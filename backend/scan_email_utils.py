import os
import json
import traceback
import base64
import re
import requests
from html import unescape

from threading import Lock
import concurrent.futures

from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as google_auth_requests
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.http import HttpError
from email.message import EmailMessage

from openai import OpenAI

from dotenv import load_dotenv


# Load environment variables
load_dotenv()

# Gmail API configuration
# If you need additional scopes, add them here
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid",
]
CLIENT_ID = os.getenv('GOOGLE_CLOUD_GMAIL_CLIENT_ID')
CLIENT_SECRET = os.getenv('GOOGLE_CLOUD_GMAIL_CLIENT_SECRET')
FLASK_KEY = os.getenv('FLASK_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
REDIRECT_URI = os.getenv('REDIRECT_URI')
LOGGED_IN_REDIRECT_URI = os.getenv('LOGGED_IN_REDIRECT_URI')
SMTP2GO_API_KEY = os.getenv('SMTP2GO_API_KEY')
MAX_EMAIL_CONCURRENCY = 25
MAX_AI_INFERENCE_CONCURRENCY = 100
EMAILS_LIMIT = 100
NUM_TRIPS_METADATA_TO_GENERATE = 5
HOTEL_RESERVATION_EMAILS_BATCH_SIZE = 20

def load_jsonl(file_path):
    with open(file_path, 'r') as f:
        return [json.loads(line) for line in f]

# def save_to_jsonl(file_path, a_list):
#     # Create directory if it doesn't exist
#     dirname = os.path.dirname(file_path)
#     if len(dirname.strip()) > 0:
#         os.makedirs(dirname, exist_ok=True)

#     # Save to JSONL file
#     with open(file_path, 'w') as f:
#         for item in a_list:
#             f.write(json.dumps(item) + '\n')

#     print(f"Saved {len(a_list)} records to {file_path}")

hotel_reservation_search_keywords = load_jsonl('hotel_reservation_search_keywords.jsonl')
hotel_reservation_search_keywords = [f'"{keyword}"' for keyword in hotel_reservation_search_keywords]
HOTEL_RESERVATION_SEARCH_QUERY = ' OR '.join(hotel_reservation_search_keywords)


def google_login():
    print("Starting Google login flow")
    #creates google login flow object
    flow = Flow.from_client_config(
        client_config={
            "web":
            {
                "client_id":CLIENT_ID
                ,"client_secret":CLIENT_SECRET
                ,"auth_uri":"https://accounts.google.com/o/oauth2/v2/auth"
                ,"token_uri":"https://oauth2.googleapis.com/token"
            }
        },
        scopes=SCOPES
    )      

    # Set redirect uri for the google callback (i.e., the route in our api that handles everything AFTER google auth)
    flow.redirect_uri = REDIRECT_URI

    # Pull authorization url (google login)
    authorization_url, state = (
        flow.authorization_url(
            access_type="offline",
            prompt="select_account",
            # include_granted_scopes="true"
        )
    )

    # Return authorization URL
    return authorization_url

def google_login_oauth2callback(session, request):
    print(f"Oauth2 Callback received.")

    state = request.args.get('state')

    # Get the base URL and replace port 5001 with 8080 to account for proxy redirect.
    redirect_uri = REDIRECT_URI # request.base_url.replace(':5001', ':8080')
    print(f"redirect_uri: {redirect_uri}")
    
    #pull the authorization response
    authorization_response = request.url
    
    #create our flow object similar to our initial login with the added "state" information
    flow = Flow.from_client_config(
        client_config={
            "web":
            {
                "client_id":CLIENT_ID
                ,"client_secret":CLIENT_SECRET
                ,"auth_uri":"https://accounts.google.com/o/oauth2/v2/auth"
                ,"token_uri":"https://oauth2.googleapis.com/token"
            }
        },
        scopes=SCOPES,
        state=state    
    )

    flow.redirect_uri = redirect_uri  
    #fetch token
    flow.fetch_token(authorization_response=authorization_response)
    #get credentials
    credentials = flow.credentials
    
    # Store the credentials in the session
    session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    
    #verify token, while also retrieving information about the user
    id_info = id_token.verify_oauth2_token(
        id_token=credentials._id_token,
        request=google_auth_requests.Request(),
        audience=CLIENT_ID
    )
    
    # Set the user information to an element of the session.
    # TODO: Do something else with this (login, store in JWT, etc)
    session["id_info"] = id_info
    session["oauth_state"] = state
    
    #redirecting to the final redirect (i.e., logged in page)
    logged_in_redirect_response = LOGGED_IN_REDIRECT_URI

    return logged_in_redirect_response

def get_gmail_service_from_session(credentials_dict):
    """Get authenticated Gmail service."""
    # Rebuild credentials object and build Gmail service
    credentials = Credentials(**credentials_dict)
    gmail_service = build('gmail', 'v1', credentials=credentials)
    return gmail_service

def increment_progress(progress, increment=15):
    progress = min(100, progress + increment)
    return progress

def scan_email(credentials_dict, id_info, progress_callback):
    progress = 0
    # Retrieve User data if needed:
    # name = id_info["name"]
    # picture = id_info["picture"]
    email = id_info["email"]

    # Retrieve credentials from session
    gmail_service = get_gmail_service_from_session(credentials_dict)

    progress = increment_progress(progress)
    progress_callback("Searching for hotel reservation emails...", progress)
    messages = search_emails(
        gmail_service,
        HOTEL_RESERVATION_SEARCH_QUERY,
        progress_callback,
        progress_main_message="Searching for hotel reservation emails...",
        progress=progress,
        max_results=EMAILS_LIMIT
    )
    if not messages or len(messages) == 0:
        raise Exception("No emails found")
    
    email_count = len(messages)
    progress_callback(f"Found {email_count} emails", progress)

    progress = increment_progress(progress)
    progress_callback("Getting full content of hotel reservation emails and checking if they are hotel reservations...", progress)
    def get_prompt_is_hotel_reservation(email_metadata):
        prompt = f"""
        Here is data for an email, is it a hotel reservation confirmation with a start date,
        end date, hotel name, room type, coming from a non-personal email, etc.?
        Make sure to only keep hotel reservations (and filter out cancellations, restaurant
        reservations and other travel related emails).

        Just answer True or False and nothing else.

        Email data:
        {email_metadata}
        """
        return prompt
    msg_ids = [message['id'] for message in messages]
    hotel_reservation_emails = get_full_hotel_reservation_emails_batch(
        msg_ids,
        credentials_dict,
        get_prompt_is_hotel_reservation,
        progress_callback,
        progress=progress,
        progress_main_message="Getting full content of hotel reservation emails and checking if they are hotel reservations..."
    )
    progress_callback(
        f"Filtered down to {len(hotel_reservation_emails)} hotel reservation emails.",
        progress,
        emails=hotel_reservation_emails
    )

    progress = increment_progress(progress)
    progress_callback(f"Getting key insights from each of the {len(hotel_reservation_emails)} hotel reservation email...", progress)
    def get_prompt_hotel_reservation_insights(msg_id):
        email_metadata = hotel_reservation_emails.get(msg_id)
        prompt = f"""
        Here is data for a hotel reservation email. Please extract key insights from the email:
        - hotel name
        - check-in, check-out dates, month of year, season of year, is this a ski-week trip? a spring break trip? a summer trip? etc.
        - location of the hotel, e.g. city, state, country, etc. what type of area is it? a beach, a mountain, a city, a town, etc.
        - number of and age of guests
        - total price, price per night, price per room, price per guest, etc.
        - is the guest a type of loyalty program member of a hotel chain? What membership level?
        - payment method (credit, debit, points, promotion, etc.)
        - type of room or suite, views, great and unusual amenities like beach front, pool, gym, michelin dining, etc. (and obvious ones like free wifi, etc.)
        - special requests made by guests (e.g. roses on arrival, baby crib, etc.)
        - probable purpose of the trip: use the room type and number of guests to infer the purpose of the trip, e.g. business, family, couple, etc. 2 queen beds and 2 adults probably isn't a couple's getaway.
        - any other key insights that would be helpful for a travel planner to know.

        Email data:
        {email_metadata}"
        """
        return prompt
    batch_hotel_reservation_key_insights = run_openai_inference_batch_with_pool(
        get_prompt_hotel_reservation_insights,
        hotel_reservation_emails.keys(),
        progress_callback,
        progress_main_message="Getting key insights from each hotel reservation email...",
        max_completion_tokens=8192,
        progress=55
    )
    for msg_id, hotel_reservation_insights in batch_hotel_reservation_key_insights.items():
        email_metadata = hotel_reservation_emails[msg_id]
        del email_metadata['body']  # If we don't have enought RAM, might be worth discarding full email body since we have key insights.
        email_metadata['key_insights'] = hotel_reservation_insights
    progress_callback(
        f"Completed getting key insights from each hotel reservation email...",
        progress,
        emails=hotel_reservation_emails
    )

    # If too much data for context window, split into batches, and cycle through them while accumulating insights.
    progress = increment_progress(progress)
    progress_callback(f"Summarizing insights from all hotel reservation emails...", progress)
    all_msg_ids = list(hotel_reservation_emails.keys())
    trip_insights = ""
    num_batches = (len(hotel_reservation_emails) + HOTEL_RESERVATION_EMAILS_BATCH_SIZE - 1) // HOTEL_RESERVATION_EMAILS_BATCH_SIZE
    for i in range(0, len(hotel_reservation_emails), HOTEL_RESERVATION_EMAILS_BATCH_SIZE):
        current_batch_msg_ids = all_msg_ids[i:i + HOTEL_RESERVATION_EMAILS_BATCH_SIZE]
        current_batch = [hotel_reservation_emails[msg_id] for msg_id in current_batch_msg_ids]
        batch_num = i // HOTEL_RESERVATION_EMAILS_BATCH_SIZE + 1
        progress_callback(
            message = f"Summarizing insights from all hotel reservation emails, processing batch of {len(current_batch)} emails {batch_num}/{num_batches} ...",
            progress=progress,
            trip_insights=trip_insights
        )

        # Call generate_trip_insights with the current batch and existing insights
        trip_insights = generate_trip_insights(
            current_batch,
            OPENAI_API_KEY,
            progress_callback,
            progress=progress,
            existing_trip_insights = trip_insights  # Pass the accumulated insights
        )

    progress = increment_progress(progress)
    progress_callback(f"Generating up to {NUM_TRIPS_METADATA_TO_GENERATE} trip recommendations...", progress, trip_insights=trip_insights)
    # hotel_reservation_key_insights # If too much data for context window, just send summarized trip_insights, works pretty well.
    # trip_jsons = generate_trips_metadatas_cerebras_openrouter([], trip_insights, NUM_TRIPS_METADATA_TO_GENERATE, progress_callback, progress=progress)
    trip_jsons = generate_trips_metadatas([], trip_insights, NUM_TRIPS_METADATA_TO_GENERATE, OPENAI_API_KEY, progress_callback, progress=progress)

    progress = 95
    progress_callback(
        message = f"Completed generating up to {NUM_TRIPS_METADATA_TO_GENERATE} trip recommendations...",
        progress=progress,
        status="completed",
        emails=hotel_reservation_emails,
        trip_insights=trip_insights,
        recommendations=trip_jsons
    )
    
    # Send trip insights by email
    progress_callback(f"Sending trip insights by email...", progress)
    progress = 100
    send_trip_insights_by_email(email, trip_insights, trip_jsons, progress_callback, progress=progress)


def send_trip_insights_by_email(to_from_email, trip_insights, trip_jsons, progress_callback, progress=100):
    """Send trip insights by email."""
    try:
        trip_jsons = json.dumps(trip_jsons, indent=4)
        email_body = f"""
        Trip Insights:
        {trip_insights}

        Trip JSONs:
        {trip_jsons}
        """

        url = "https://api.smtp2go.com/v3/email/send" 

        headers = {
            "Content-Type": "application/json",
            'X-Smtp2go-Api-Key': SMTP2GO_API_KEY,
            "accept": "application/json"
        }

        payload = {
            "to": [to_from_email],
            "sender": "alexis@goviammo.com ",
            "subject": "Trip Insights and Recommendations",
            "text_body": email_body
        }

        response = requests.post(url, json=payload, headers=headers)

        if response.status_code != 200:
            progress_callback(
                message = f"Failed to send email with error: {response.text}",
                progress=100,
                status="failed"
            )
            return

        progress_callback(
            message = "Email sent successfully",
            progress=100,
            status="completed"
        )
    except Exception as e:
        e_trace = traceback.format_exc()
        progress_callback(
            message = f"Failed to send email with error: {e_trace}",
            progress=100,
            status="failed"
        )
    

def search_emails(service, query, progress_callback, progress_main_message="", progress=5, max_results=500):
    """Search for emails matching the query.
    
    Args:
        service: Authenticated Gmail API service instance.
        query: String used to filter messages matching specific criteria.
        max_results: Maximum number of results to return (default 500)
        
    Returns:
        List of messages that match the criteria
    """
    try:
        # Initialize empty list for messages and nextPageToken
        messages = []
        next_page_token = None
        
        # Keep fetching pages until all results are retrieved or max_results is reached
        while True:
            # Request a page of results
            result = service.users().messages().list(
                userId='me',
                q=query,
                pageToken=next_page_token,
                maxResults=min(max_results - len(messages), 100)  # Gmail API allows max 100 per request
            ).execute()
            
            # Get messages from this page
            page_messages = result.get('messages', [])
            if not page_messages:
                break
                
            # Add messages to our list
            messages.extend(page_messages)
            progress_callback(f"{progress_main_message} Retrieved {len(messages)} emails IDs of max {max_results}...", progress)
            
            # Check if we've reached the desired number of results
            if len(messages) >= max_results:
                progress_callback(f"{progress_main_message} Reached maximum of {max_results} emails", progress)
                break
                
            # Get token for next page or exit if no more pages
            next_page_token = result.get('nextPageToken')
            if not next_page_token:
                break
        
        return messages
        
    except Exception as error:
        progress_callback(f"{progress_main_message} An error occurred: {error}\nstack_trace: {traceback.format_exc()}", progress)
        return []

def get_email_metadatas_batch(msg_ids, credentials_dict, progress_callback, progress_main_message="", progress=15, max_workers=MAX_EMAIL_CONCURRENCY):
    """Get email metadata for multiple message IDs in a batch request."""
    results = []
    results_lock = Lock()
    
    def fetch_single_message(msg_id, idx, len_emails):
        """Process a single message and return its metadata."""
        try:
            service = get_gmail_service_from_session(credentials_dict)

            response = service.users().messages().get(
                userId='me',
                id=msg_id,
                format='metadata',
                metadataHeaders=['Subject', 'From', 'To', 'Date', 'Reply-To', 'CC', 'BCC', 'In-Reply-To']
            ).execute()
        
            # Process the response the same way as the individual method
            headers = response['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown Date')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
            recipient = next((h['value'] for h in headers if h['name'] == 'To'), 'Unknown Recipient')
            reply_to = next((h['value'] for h in headers if h['name'] == 'Reply-To'), 'Unknown Reply-To')
            cc = next((h['value'] for h in headers if h['name'] == 'CC'), 'Unknown CC')
            bcc = next((h['value'] for h in headers if h['name'] == 'BCC'), 'Unknown BCC')
            in_reply_to = next((h['value'] for h in headers if h['name'] == 'In-Reply-To'), 'Unknown In-Reply-To')
            
            email_metadata = {
                'id': msg_id,
                'subject': subject,
                'date': date,
                'sender': sender,
                'recipient': recipient,
                'reply_to': reply_to,
                'cc': cc,
                'bcc': bcc,
                'in_reply_to': in_reply_to,
            }

            with results_lock:
                results.append(email_metadata)
                fetched_count = len(results)
                if fetched_count % max_workers == 0:
                    progress_callback(f"{progress_main_message} Fetched {fetched_count} / {len_emails} email metadatas...", progress)
            
            return email_metadata
        
        except HttpError as error:
            progress_callback(f"{progress_main_message} Error fetching message {msg_id}: {error}", progress)
            return None
    
    # results = [fetch_single_message(msg_id, idx) for idx, msg_id in enumerate(msg_ids)]

    # Create a thread pool with limited concurrency
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks to the executor
        len_emails = len(msg_ids)
        futures = {executor.submit(fetch_single_message, msg_id, idx, len_emails): msg_id for idx, msg_id in enumerate(msg_ids)}
        
        # Process results as they complete (optional)
        for future in concurrent.futures.as_completed(futures):
            msg_id = futures[future]
            try:
                # This will re-raise any exceptions from the task
                future.result()
            except Exception as exc:
                progress_callback(f"{progress_main_message} Message {msg_id} generated an exception: {exc}", progress)
    
    return results

def run_openai_inference(prompt, model="o4-mini", max_completion_tokens=4096, temperature=1.0, top_p=1.0):
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    response = openai_client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        max_completion_tokens=max_completion_tokens,
        temperature=temperature,
        top_p=top_p
    )

    return response.choices[0].message.content

def run_openai_inference_batch_with_pool(
    get_prompt_f,
    prompt_ids,
    progress_callback,
    progress_main_message = "Processing prompts...",
    progress=20,
    max_workers=MAX_AI_INFERENCE_CONCURRENCY,
    model="o4-mini",
    max_completion_tokens=4096,
    ):
    """Process multiple prompts with OpenAI API using a thread pool."""
    results = {}
    results_lock = Lock() # To safely update the shared results dictionary
    completed_count = 0
    total_prompts = len(prompt_ids)

    def process_single_prompt(prompt_id, get_prompt_f):
        nonlocal completed_count
        prompt_text = get_prompt_f(prompt_id)
        try:
            response = run_openai_inference(prompt_text, model=model, max_completion_tokens=max_completion_tokens)
            with results_lock:
                results[prompt_id] = response
                completed_count += 1
                if completed_count % max_workers == 0:
                    progress_callback(f"{progress_main_message} Completed {completed_count} / {total_prompts}", progress)
            return prompt_id, response
        except Exception as e:
            with results_lock:
                results[prompt_id] = f"ERROR: {str(e)}"
                completed_count += 1
                progress_callback(f"Error processing prompt ID {prompt_id}: {e}. Completed {completed_count} / {total_prompts}.", progress)
            return prompt_id, f"ERROR: {str(e)}"

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit tasks: executor.submit(function, arg1, arg2, ...)
        future_to_prompt_id = {executor.submit(process_single_prompt, pid, get_prompt_f): pid for pid in prompt_ids}

        for future in concurrent.futures.as_completed(future_to_prompt_id):
            prompt_id_completed = future_to_prompt_id[future]
            try:
                future.result()
            except Exception as exc:
                progress_callback(f'Prompt ID {prompt_id_completed} generated an exception in future: {exc}', progress)
                with results_lock:
                    if prompt_id_completed not in results:
                         results[prompt_id_completed] = f"ERROR: {str(exc)}"

    return results

def get_full_email_batch(
    msg_ids,
    credentials_dict,
    progress_callback,
    progress_main_message="",
    progress=20,
    max_workers=MAX_EMAIL_CONCURRENCY,
    ):
    """Get full email for multiple message IDs in a batch request."""
    results = {}
    results_lock = Lock()
    
    def fetch_single_full_message(msg_id, idx, len_emails):
        """Process a single message and return its metadata."""
        try:
            gmail_service = get_gmail_service_from_session(credentials_dict)

            response = gmail_service.users().messages().get(
                userId='me',
                id=msg_id,
                format='full'
            ).execute()
        
            # Process the response the same way as the individual method
            headers = response['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown Date')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
            recipient = next((h['value'] for h in headers if h['name'] == 'To'), 'Unknown Recipient')
            reply_to = next((h['value'] for h in headers if h['name'] == 'Reply-To'), 'Unknown Reply-To')
            cc = next((h['value'] for h in headers if h['name'] == 'CC'), 'Unknown CC')
            bcc = next((h['value'] for h in headers if h['name'] == 'BCC'), 'Unknown BCC')
            in_reply_to = next((h['value'] for h in headers if h['name'] == 'In-Reply-To'), 'Unknown In-Reply-To')

            def extract_text_from_html(html):
                """Extract plain text from HTML content."""
                # Remove HTML tags
                text = re.sub(r'<[^>]+>', ' ', html)
                # Decode HTML entities
                text = unescape(text)
                # Replace multiple whitespace with single space
                text = re.sub(r'\s+', ' ', text)
                # Remove leading/trailing whitespace
                text = text.strip()
                return text

            def get_text_from_part(part):
                """Recursively extract text from email parts."""
                if part.get('mimeType') == 'text/plain' and 'data' in part.get('body', {}):
                    return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                if part.get('mimeType') == 'text/html' and 'data' in part.get('body', {}):
                    html = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                    return extract_text_from_html(html)
                if 'parts' in part:  # Check for nested parts
                    subpart_texts = [get_text_from_part(subpart) for subpart in part['parts']]
                    subpart_texts = [subpart_text for subpart_text in subpart_texts if subpart_text is not None]
                    return ' '.join(subpart_texts)

            body = get_text_from_part(response['payload'])
            body = body if body else "Unknown body"
            
            email_metadata = {
                'id': msg_id,
                'subject': subject,
                'date': date,
                'sender': sender,
                'recipient': recipient,
                'reply_to': reply_to,
                'cc': cc,
                'bcc': bcc,
                'in_reply_to': in_reply_to,
                'body': body,
            }

            with results_lock:
                results[msg_id] = email_metadata
                fetched_count = len(results)            
                if fetched_count % max_workers == 0:
                    progress_callback(f"{progress_main_message} Fetched {fetched_count} / {len_emails} full email contents...", progress)
            
            return email_metadata
        
        except HttpError as error:
            progress_callback(f"{progress_main_message} Error fetching message {msg_id}: {error}", progress)
            return None

    # Create a thread pool with limited concurrency
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks to the executor
        len_emails = len(msg_ids)
        futures = {executor.submit(fetch_single_full_message, msg_id, idx, len_emails): msg_id for idx, msg_id in enumerate(msg_ids)}
        
        # Process results as they complete (optional)
        for future in concurrent.futures.as_completed(futures):
            msg_id = futures[future]
            try:
                # This will re-raise any exceptions from the task
                future.result()
            except Exception as exc:
                progress_callback(f"Message {msg_id} generated an exception: {exc}", progress)
    
    return results

def get_full_hotel_reservation_emails_batch(
    msg_ids,
    credentials_dict,
    get_prompt_from_email_metadata_f,
    progress_callback,
    progress_main_message="",
    progress=20,
    max_workers=MAX_EMAIL_CONCURRENCY,
    model="o4-mini",
    max_completion_tokens=4096,
    ):
    """Get full email for multiple message IDs in a batch request."""
    results = {}
    results_lock = Lock()
    completed_count = 0
    
    def fetch_single_full_message(msg_id, idx, len_emails):
        """Process a single message and return its metadata."""
        try:
            gmail_service = get_gmail_service_from_session(credentials_dict)

            response = gmail_service.users().messages().get(
                userId='me',
                id=msg_id,
                format='full'
            ).execute()
        
            # Process the response the same way as the individual method
            headers = response['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown Date')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
            recipient = next((h['value'] for h in headers if h['name'] == 'To'), 'Unknown Recipient')
            reply_to = next((h['value'] for h in headers if h['name'] == 'Reply-To'), 'Unknown Reply-To')
            cc = next((h['value'] for h in headers if h['name'] == 'CC'), 'Unknown CC')
            bcc = next((h['value'] for h in headers if h['name'] == 'BCC'), 'Unknown BCC')
            in_reply_to = next((h['value'] for h in headers if h['name'] == 'In-Reply-To'), 'Unknown In-Reply-To')

            def extract_text_from_html(html):
                """Extract plain text from HTML content."""
                # Remove HTML tags
                text = re.sub(r'<[^>]+>', ' ', html)
                # Decode HTML entities
                text = unescape(text)
                # Replace multiple whitespace with single space
                text = re.sub(r'\s+', ' ', text)
                # Remove leading/trailing whitespace
                text = text.strip()
                return text

            def get_text_from_part(part):
                """Recursively extract text from email parts."""
                if part.get('mimeType') == 'text/plain' and 'data' in part.get('body', {}):
                    return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                if part.get('mimeType') == 'text/html' and 'data' in part.get('body', {}):
                    html = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                    return extract_text_from_html(html)
                if 'parts' in part:  # Check for nested parts
                    subpart_texts = [get_text_from_part(subpart) for subpart in part['parts']]
                    subpart_texts = [subpart_text for subpart_text in subpart_texts if subpart_text is not None]
                    return ' '.join(subpart_texts)

            body = get_text_from_part(response['payload'])
            body = body if body else "Unknown body"
            
            email_metadata = {
                'id': msg_id,
                'subject': subject,
                'date': date,
                'sender': sender,
                'recipient': recipient,
                'reply_to': reply_to,
                'cc': cc,
                'bcc': bcc,
                'in_reply_to': in_reply_to,
                'body': body,
            }

            # Immediately check if the email is a hotel reservation and discard rest to save memory.
            prompt_text = get_prompt_from_email_metadata_f(email_metadata)
            response = run_openai_inference(prompt_text, model=model, max_completion_tokens=max_completion_tokens)

            nonlocal completed_count
            completed_count += 1
            kept_count = len(results)
            if completed_count % max_workers == 0:
                progress_callback(f"{progress_main_message} Fetched and checked {completed_count} / {len_emails} full email contents, {kept_count} kept...", progress)

            if "True" == response:
                with results_lock:
                    results[msg_id] = email_metadata
            
            return
        
        except HttpError as error:
            progress_callback(f"{progress_main_message} Error fetching message {msg_id}: {error}", progress)
            return None

    # Create a thread pool with limited concurrency
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks to the executor
        len_emails = len(msg_ids)
        futures = {executor.submit(fetch_single_full_message, msg_id, idx, len_emails): msg_id for idx, msg_id in enumerate(msg_ids)}
        
        # Process results as they complete (optional)
        for future in concurrent.futures.as_completed(futures):
            msg_id = futures[future]
            try:
                # This will re-raise any exceptions from the task
                future.result()
            except Exception as exc:
                progress_callback(f"Message {msg_id} generated an exception: {exc}", progress)
    
    return results

def generate_trip_insights(trip_message_datas, openai_api_key, progress_callback, progress=65, existing_trip_insights = "") -> str:
    """
    Returns a list of trip information JSON objects.
    """

    if not openai_api_key:
        print("Warning: OPENAI_API_KEY environment variable not set. Skipping LLM keyword extraction.")
        return None
    
    # Define a prompt template for hotel characteristics
    prompt = f"""
    Based on the following hotel reservation email messages and the existing trip insights, please analyze the typical patterns of
    the user's travel preferences and generate a list of types of trips that the user has taken. For each type of trip, include the
    following key information:
    - destination
    - time of year, e.g. ski week, spring break, summer, end of year holidays, Thanksgiving, Memorial Day, Labor Day, etc.
    - length of the trip
    - number of guests and type of guests, e.g. adults, children, infants, etc.
    - number of times the user did a similar trip
    - likely purpose of the trip
    - total budget with $ signs, e.g. "$$$$",  "$$$", "$$", "$", etc. with "$$$$" being the highest budget.
    - preferred hotel, keep specifics e.g. "Hilton Honolulu", "Hyatt Waikiki", "St. Regis San Francisco", etc.
    - preferred hotel chains, keep specifics e.g. "Hilton", "Marriott", "Hyatt", "St. Regis", "Rosewood", "Relais & Chateaux", "Four Seasons", "Leading Hotels of the World", etc.
    - preferred hotel characteristics, keep specifics e.g. "family friendly", "ski-in-ski-out", "beach front", "pool", "gym", "spa", "free Wi-Fi", "free breakfast", "free airport shuttle", "free parking", etc.
    - preferred room types, keep specifics e.g. "1 King bed Suite", "1 room with King bed and 1 room with 2 queens", "2 Queen beds", "Crib", "Pool view", "Garden view", "Ocean view", "Mountain view", etc.
    - preferred amenities, keep specifics e.g. "ski-in-ski-out", "beach front", "pool", "gym", "spa", "free Wi-Fi", "free breakfast", "free airport shuttle", "free parking", etc.
    - preferred activities, keep specifics e.g. "skiing", "snowboarding", "hiking", "surfing", "golfing", "scuba diving", "snorkeling", "water sports", "etc."
    - preferred dining experiences, keep specifics e.g. "fine dining", "casual dining", "cafe", "pub", "italian", "japanese", "mexican", "etc."
    - preferred payment method, keep specifics e.g. "credit card", "debit card", "hyatt points", "marriott points", "etc."
    - key details from each trip in this trip type
    - any other information that would be helpful for a travel planner to know.

    Try to generate 5-10 trip types with at least 3 trips per trip type unless you don't have enough trips. If you don't have enough
    trips, start by creating trip types based off of individual trips.

    If you already have generated some trip insights, please add new trip types or merge existing trip types. When merging trip type
    information, make sure to keep track of the total number of days for all trips in that trip type, and any other salient details.
    Rank your trip types with a higher total number of days and total number of trips higher in your list. Keep the number of trip types
    between below or equal to 10.

    You're output should be a self-sufficient list of trip types and their key information (not just an addition to an existing list
    of trip insights).

    Return just list of the types of trips and their key information (as highlighted above).

    Here is the existing trip insights you have already started to generate:
    {existing_trip_insights}

    Here are the new hotel reservation emails you need to analyze:
    {trip_message_datas}
    """

    try:
        response_content = run_openai_inference(prompt, max_completion_tokens=100000)
        if not response_content:
            progress_callback(f"LLM did not return a response to generate trip insights", progress)
            return None
    except Exception as e:
        progress_callback(f"LLM did not return a response to generate trip insights: {e}", progress)
        return None
    
    return response_content

def generate_trips_metadatas(trip_message_datas, trip_insights, num_trips, openai_api_key, progress_callback, progress=100) -> str:
    """
    Returns a list of trip information JSON objects.
    """

    if not openai_api_key:
        print("Warning: OPENAI_API_KEY environment variable not set. Skipping LLM keyword extraction.")
        return None
        
    # Define a prompt template for hotel characteristics
    prompt = f"""
    Based on the following hotel reservation email messages and the following trip insights, please analyze the typical patterns of the user's
    travel preferences and generate a list of great future possile trips as a json list of distionaries with up to {num_trips} trip objects like
    the one below corresponding to the user's travel preferences. Please only return valid JSON and nothing else - no explanations or text before
    or after the JSON. Please only use the json fields that are present in the example trip json objects below - don't add extra json fields, add
    extra info in notes field for example. Make sure the dates are in the future and correspond to the preferred destinations.

    Make sure to find and account for the following information in the trip json objects:
    - preferred destinations
    - preferred travel dates for preferred destinations
    - number of guests and type of guests for those preferred destinations and dates, try using age of guests to determine if they are adults or children.
    - purpose of the trip, e.g. "Family vacation", "Business trip", "Solo travel", "Couple's getaway", etc. Try using past room types for preferred destinations to determine purpose, e.g. 1 room with 2 queen beds probably isn't a couple's getaway purpose trip.
    - total budget with $ signs, e.g. "$$$$",  "$$$", "$$", "$", etc. with "$$$$" being the highest budget.
    - Preferred hotel characteristics to add to notes field, e.g. "Family friendly", "Ski-in-ski-out", "Beachfront", "Business class", etc.
    - Preferred hotel chains to add to notes field, e.g. "Hilton", "Marriott", "Hyatt", "St. Regis", "Rosewood", "Relais & Chateaux", "Four Seasons", "Leading Hotels of the World", etc.
    - Preferred room types to add to notes field, e.g. "1 King bed Suite", "1 room with King bed and 1 room with 2 queens", "2 Queen beds", "Crib", "Pool view", "Garden view", "Ocean view", "Mountain view", etc.
    - Preferred amenities to add to notes field, e.g. "Free Wi-Fi", "Free breakfast", "Free airport shuttle", "Free parking", "Free Wi-Fi", "Free breakfast", "Free airport shuttle", "Free parking", etc.
    - Preferred hotel features to add to notes field, e.g. "Spa", "Gym", "Pool", "Beachfront", "Ski-in-ski-out", "Walkable", "Ocean view", "Mountain view", "Garden view", etc.
    - Preferred activities to add to notes field, e.g. "Hiking", "Skiing", "Cross Country Skiing", "Backcountry Skiing & Snowboarding", "Surfing", "Golfing", "Scuba diving", "Snorkeling", "Water sports", "Sailing", "Fishing", "etc."
    - Preferred dining experiences to add to notes field, e.g. "Fine dining", "Casual dining", "Fast food", "Cafe", "Bar", "Pub", "Italian", "Japanese", "Mexican", "American", "French", "Spanish", "etc."
    - Preferred children activities to add to notes field, e.g. "Kids club", "Kids activities", "Kids pool", "Kids spa", "Kids gym", "Kids beach", "Kids mountain", "Kids garden", "etc."
    - any other information that would be helpful for a travel planner to know.

    Example returned list of with 1 trip object (up to {num_trips} great):
    [
        {{
            "name": "Tahoe Family",
            "startDate": "2026-02-18T07:00:00.000Z",
            "endDate": "2026-02-21T07:00:00.000Z",
            "destination": {{
                "city": "Palisades Tahoe",
                "state": "CA",
                "country": "USA"
            }},
            "numberOfGuests": {{
                "$numberInt": "4"
            }},
            "notes": "Ski-in-ski-out, family friendly, 1 room with 2 adults with one king bed, 1 room with 2 kids and 2 queen beds",
            "totalBudget": "$$$$",
            "purpose": "Family vacation"
        }}
    ]

    Here are the trip insights you have already generated:
    {trip_insights}

    Trip message datas:
    {trip_message_datas}
    """

    try:
        response_content = run_openai_inference(prompt, max_completion_tokens=100000)
        if not response_content:
            progress_callback(f"LLM did not return a response to generate trip insights", progress)
            return None
    except Exception as e:
        progress_callback(f"LLM did not return a response to generate trip insights: {e}", progress)
        return None
    
    # Try to parse the response as JSON
    try:
        # Parse the JSON
        trip_jsons = json.loads(response_content)
        return trip_jsons
    except json.JSONDecodeError as e:
        progress_callback(f"Error parsing JSON response: {e} Raw response: {response_content}", progress)
        return None
