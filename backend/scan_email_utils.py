import os
import json
import traceback
import base64
import re
import requests
from html import unescape
from datetime import datetime

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
EMAILS_LIMIT = 4000
NUM_TRIPS_METADATA_TO_GENERATE = 5
HOTEL_RESERVATION_EMAILS_BATCH_SIZE = 20
MAX_EMAILS_TO_GROUP = 140
NUM_RESERVATION_BULLETS = 12
MAX_NUM_TRIP_GROUPS = 15
MAX_YEARS_BACK = 10

def load_jsonl(file_path):
    with open(file_path, 'r') as f:
        return [json.loads(line) for line in f]

# def save_to_txt(file_path, text):
#     # Create directory if it doesn't exist
#     dirname = os.path.dirname(file_path)
#     if len(dirname.strip()) > 0:
#         os.makedirs(dirname, exist_ok=True)

#     # Save to JSONL file
#     with open(file_path, 'w') as f:
#         f.write(text)

#     print(f"Saved {len(text)} characters to {file_path}")

# def load_from_txt(file_path):
#     with open(file_path, 'r') as f:
#         return f.read()

# def save_emails_to_jsonl(file_path, emails_dict):
#     # Create directory if it doesn't exist
#     dirname = os.path.dirname(file_path)
#     if len(dirname.strip()) > 0:
#         os.makedirs(dirname, exist_ok=True)

#     # Save to JSONL file
#     with open(file_path, 'w') as f:
#         for _id, email in emails_dict.items():
#             f.write(json.dumps(email) + '\n')

#     print(f"Saved {len(emails_dict)} emails to {file_path}")

# def load_emails_from_jsonl(file_path):
#     with open(file_path, 'r') as f:
#         emails = {}
#         for line in f:
#             email = json.loads(line)
#             emails[email['id']] = email
#         return emails

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

def increment_progress(progress, increment=10):
    progress = min(100, progress + increment)
    return progress

def scan_email(credentials_dict, id_info, progress_callback):

    progress = 0
    progress_callback("Starting email scan...", progress)

    try:

        # Retrieve User data if needed:
        # name = id_info["name"]
        # picture = id_info["picture"]
        email = id_info["email"]

        # if not os.path.exists('./email_data/v0/hotel_reservation_emails.jsonl'):

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
        #     save_emails_to_jsonl('./email_data/v0/hotel_reservation_emails.jsonl', hotel_reservation_emails)
        # else:
        #     hotel_reservation_emails = load_emails_from_jsonl('./email_data/v0/hotel_reservation_emails.jsonl')
        
        progress_callback(
            f"Filtered down to {len(hotel_reservation_emails)} hotel reservation emails.",
            progress,
            emails=hotel_reservation_emails
        )

        # if not os.path.exists('./email_data/v0/hotel_reservation_emails_key_insights.jsonl'):

        progress = increment_progress(progress)
        progress_callback(f"Getting key insights from each of the {len(hotel_reservation_emails)} hotel reservation email...", progress)
        def get_prompt_hotel_reservation_insights(msg_id):
            email_metadata = hotel_reservation_emails.get(msg_id)
            prompt = f"""
            Here is data for a hotel reservation email. Please extract the top {NUM_RESERVATION_BULLETS} most important or surprising features from the email:
            - (super important) what is location known for and does hotel make it easy to do it? e.g. golfing in Scotland, skiing in Aspen, surfing in Bali, hiking Grand Canyon, etc.
            - (super important) is there something going on in that location at that time of the year? e.g. Coachella Music Festival, Cannes Film Festival, Art Basel Miami, Vancouver TED Conference, etc.
            - (super important) for this general hotel location, is it peak season, shoulder season, off season? e.g. February in Aspen is peak (good snow), August in Florida is off peak (too warm), etc.
            - (super important) precise hotel name, location and description, e.g. "Ritz-Carlton in Costa Rica", "Four Seasons in Bali", etc.
            - (super important) check-in and check-out date, e.g. "2024-11-24 to 2024-11-30"
            - (super important) number and types of rooms, number and type of beds, with room specifics, e.g. 1 room with 1 king connecting to 1 room with 2 queens, 2 room suite each with two queens, king bed premium ocean view (e.g. ocean view, city view, etc.), 3+ room suite, 3+ room standalone villa, etc.
            - (super important) number of and age of guests, adults, children, seniors, dogs or pets, etc. How does this work with beds and rooms? e.g. 2 adults in king room and 2 children in room with 2 queens, etc.
            - (important) special requests made by guests, e.g. roses on arrival, baby crib, dog bed and dog bowls, etc.
            - (important) what is hotel chain? e.g. "Hilton", "Marriott", "Hyatt", "St. Regis", "Rosewood", "Relais & Chateaux", "Four Seasons", "Leading Hotels of the World", etc.
            - (important) cost per night and total cost of the reservation.
            - price category of hotel? e.g. "$$$$", "$$$", "$", "$", etc. Is it always hyper luxury "$$$$$" (more than $2000/night)?
            - surprising hotel amenities like private pool for each room, michelin dining, hot water springs, famous surf spot walkable access, etc. Don't include obvious amenities like high speed wifi, TV, parking, etc.
            - surprising dining experiences e.g. michelin star, exclusively raw dining, etc.
            - surprising type of hotel, e.g. villa only, romantic only, spa/wellness only, surf only, treehouse, ice hotel, fantasy/movie themed (like Disney themed resorts), historical, modern/contemporary, boutique, hyper-luxury, eco/green, etc.
            - probable purpose of the trip: use the room type and number of guests to infer the purpose of the trip, e.g. business, family, couple, etc. 2 queen beds and 2 adults probably isn't a couple's getaway.
            - any other key insights that would be helpful for a travel planner to know.

            Example output:
            • Location: Tahoe Palisades known for skiing during this period of the year
            • Special events: Tahoe Palisades World Cup Ski Competition
            • Time of year: Peak winter season (Feb) in Tahoe, most probably during ski week school break
            • Destinations: Everline Resort & Spa in Olympic Valley, CA
            • Check-in and check-out dates: 2024-02-22 to 2024-02-27
            • Rooms: Suite with 1 king room and room with 2 queens
            • Guests: 2 adults and 2 children (ages 10 and 12), likely family with 2 adults in king room and 2 children in room with 2 queens
            • Special Requests: accommodation for 2 dogs
            • Hotel Chain: World of Hyatt
            • Cost per night $1,000 and total cost $5,000
            • Surprising hotel amenities: outside hot pools and hot tubs at freezing temperatures
            • Hotel style: ski-in/ski-out

            Don't use more than {NUM_RESERVATION_BULLETS} bullet points, and use only one line per bullet point, and use no more than 10 words per bullet point.

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
            progress=progress
        )
        for msg_id, hotel_reservation_insights in batch_hotel_reservation_key_insights.items():
            email_metadata = hotel_reservation_emails[msg_id]
            del email_metadata['body']  # If we don't have enought RAM, might be worth discarding full email body since we have key insights.
            email_metadata['key_insights'] = hotel_reservation_insights
        
        progress = increment_progress(progress)
        progress_callback(f"Getting length of stay for each of the {len(hotel_reservation_emails)} hotel reservations...", progress)
        def get_prompt_hotel_reservation_stay_length(msg_id):
            email_metadata = hotel_reservation_emails.get(msg_id)
            prompt = f"""
            Here is data for a hotel reservation email. Please extract the length of stay in days.
            
            Please don't return anything else than integer number.

            If you can't extract the length of the stay, return 0.

            Email data:
            {email_metadata}"
            """
            return prompt
        batch_hotel_reservation_stay_length = run_openai_inference_batch_with_pool(
            get_prompt_hotel_reservation_stay_length,
            hotel_reservation_emails.keys(),
            progress_callback,
            progress_main_message="Getting stay length from each hotel reservation email...",
            max_completion_tokens=4096,
            progress=progress
        )
        for msg_id, stay_length in batch_hotel_reservation_stay_length.items():
            email_metadata = hotel_reservation_emails[msg_id]
            try:
                email_metadata['stay_length'] = int(stay_length)
            except Exception:
                email_metadata['stay_length'] = 0
        
        progress = increment_progress(progress)
        progress_callback(f"Getting stay year for each of the {len(hotel_reservation_emails)} hotel reservations...", progress)
        def get_prompt_hotel_reservation_stay_year(msg_id):
            email_metadata = hotel_reservation_emails.get(msg_id)
            prompt = f"""
            Here is data for a hotel reservation email. Please extract the year of the stay.
            
            Please don't return anything else than integer number.

            If you can't extract the year of the stay, return 0.

            Email data:
            {email_metadata}"
            """
            return prompt
        batch_hotel_reservation_stay_year = run_openai_inference_batch_with_pool(
            get_prompt_hotel_reservation_stay_year,
            hotel_reservation_emails.keys(),
            progress_callback,
            progress_main_message="Getting stay year from each hotel reservation email...",
            max_completion_tokens=4096,
            progress=progress
        )
        for msg_id, stay_year in batch_hotel_reservation_stay_year.items():
            email_metadata = hotel_reservation_emails[msg_id]
            try:
                email_metadata['stay_year'] = int(stay_year)
            except Exception:
                email_metadata['stay_year'] = 0

        #     save_emails_to_jsonl('./email_data/v0/hotel_reservation_emails_key_insights.jsonl', hotel_reservation_emails)
        # else:
        #     hotel_reservation_emails = load_emails_from_jsonl('./email_data/v0/hotel_reservation_emails_key_insights.jsonl')
        
        progress_callback(
            f"Completed getting key insights and stay length from each hotel reservation email...",
            progress,
            emails=hotel_reservation_emails
        )

        # Only keep reservations from past 10 years.
        hotel_reservation_emails_list = [email for email in hotel_reservation_emails.values() if email['stay_year'] >= (datetime.now().year - MAX_YEARS_BACK)]

        # Sort emails by descending stay length
        hotel_reservation_emails_list = sorted(hotel_reservation_emails_list, key=lambda x: x['stay_length'], reverse=True)

        # Keep |MAX_EMAILS_TO_GROUP| longest trips and remove the rest
        hotel_reservation_emails_list = hotel_reservation_emails_list[:MAX_EMAILS_TO_GROUP]

        # if not os.path.exists('./email_data/v0/hotel_reservation_groups.txt'):

        # If too much data for context window, split into batches, and cycle through them while accumulating insights.
        progress = increment_progress(progress)
        progress_callback(f"Summarizing insights from all hotel reservation emails...", progress)
        trip_insights = ""
        num_batches = (len(hotel_reservation_emails_list) + HOTEL_RESERVATION_EMAILS_BATCH_SIZE - 1) // HOTEL_RESERVATION_EMAILS_BATCH_SIZE
        for i in range(0, len(hotel_reservation_emails_list), HOTEL_RESERVATION_EMAILS_BATCH_SIZE):
            current_batch = hotel_reservation_emails_list[i:i + HOTEL_RESERVATION_EMAILS_BATCH_SIZE]
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
            trip_insights = generate_trip_insights( # Run extra time without any emails to promote reshuffling of trip groups
                [],
                OPENAI_API_KEY,
                progress_callback,
                progress=progress,
                existing_trip_insights = trip_insights  # Pass the accumulated insights
            )
            
        #     save_to_txt('./email_data/v0/hotel_reservation_groups.txt', trip_insights)
        # else:
        #     trip_insights = load_from_txt('./email_data/v0/hotel_reservation_groups.txt')

        progress = increment_progress(progress)
        progress_callback(f"Generating up to {NUM_TRIPS_METADATA_TO_GENERATE} trip recommendations...", progress, trip_insights=trip_insights)
        # hotel_reservation_key_insights # If too much data for context window, just send summarized trip_insights, works pretty well.
        # trip_jsons = generate_trips_metadatas_cerebras_openrouter([], trip_insights, NUM_TRIPS_METADATA_TO_GENERATE, progress_callback, progress=progress)
        trip_jsons = generate_trips_metadatas(trip_insights, NUM_TRIPS_METADATA_TO_GENERATE, OPENAI_API_KEY, progress_callback, progress=progress)

        progress = 100
        progress_callback(
            message = f"Completed generating up to {NUM_TRIPS_METADATA_TO_GENERATE} trip recommendations...",
            progress=progress,
            status="completed",
            emails=hotel_reservation_emails,
            trip_insights=trip_insights,
            recommendations=trip_jsons
        )
        
        # # Send trip insights by email
        # progress_callback(f"Sending trip insights by email...", progress)
        # progress = 100
        # send_trip_insights_by_email(email, trip_insights, trip_jsons, progress_callback, progress=progress)
    except Exception as e:
        e_trace = traceback.format_exc()
        progress_callback(
            message = f"Failed to generate trip recommendations with error: {e_trace}",
            progress=progress,
            status="failed"
        )


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
                progress=progress,
                status="failed"
            )
            return

        progress_callback(
            message = "Email sent successfully",
            progress=progress,
            status="completed"
        )
    except Exception as e:
        e_trace = traceback.format_exc()
        progress_callback(
            message = f"Failed to send email with error: {e_trace}",
            progress=progress,
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
    
    prompt = f"""

    Try to generate up to {MAX_NUM_TRIP_GROUPS} group of trips with at least 3 trips per group unless you don't have enough trips. If you don't have enough
    trips, start by creating trip groups based off of individual trips. Track and rank features by most important, surprising, or repeating 
    features, keep as much detail as possible.

    If you also get previously generated trip groups, please either:
    - merge existing trip groups
    - reshuffle trip groups
    - create new trip groups
    - don't just list what new trips to add to existing trip groups, please relist full self-contained trip groups from scratch every time
    For each group of trips, keep track of each one of their trips and for each trip, keep track of their top 5 most important, surprising, or repeating
    features so that each trip can easily be merged or reshuffled into other trip groups. Please also track total number of deduped days and total number of trips
    for each trip group. Trip features marked as (important) or (super important) should always be listed for that trip and its trip group with (super important)
    listed first. When merging or reshuffling trip groups, make sure to keep all the trips (old and new) long with all the features of each trip in that group. Don't
    add the same trip in multiple groups (check for overlapping dates and location). Also don't add the same trip multiple times in the same group (check for overlapping
    dates and location). Rank your trip groups by descending most important, surprising, or repeating features as well as total number of deduped days and total number
    of trips. Keep the number of trip groups to {MAX_NUM_TRIP_GROUPS} or less. A single hotel reservation can be a trip group if it has enough days. When merging or reshuffling trip groups,
    make sure not to delete any information that would be helpful for a travel planner to know. Feel free to rerank trips as you add, merge and reshuffle trip groups.
    When reshuffling, feel free to move trips to different trip groups that would be a better match. Use important, surprising and repeating features to create a title for trip group.

    You can group trips with the following features:
    - (super important) for location, is there something going on at that time of the year? e.g. Coachella Music Festival, Cannes Film Festival, Art Basel Miami, Vancouver TED Conference, etc.
    - (super important) close in dates (not further than 6 days apart) and location by car/train/airplane, e.g. Mar 24-28 2024 in Florence Italy and Mar 26-30 2024 in Pisa Italy, or Apr 14-18 2023 in Rome Italy and Apr 20-23 2023 in Paris France
    - (super important) what is location known for and does hotel make it easy to do it? e.g. golfing in Scotland, skiing in Aspen, surfing in Bali, etc.
    - (important) number and types of rooms, number and type of beds, with room specifics, e.g. 1 room with 1 king connecting to 1 room with 2 queens, 2 room suite each with two queens, king bed premium ocean view (e.g. ocean view, city view, etc.), 3+ room suite, 3+ room standalone villa, etc.
    - (important) number of and age of guests, adults, children, seniors, dogs or pets, etc. How does this work with beds and rooms? e.g. 2 adults in king room and 2 children in room with 2 queens, etc.
    - (important) repeating in season, e.g. Thanksgiving trips, Summer trips, etc. 
    - (important) for location, is it peak season, shoulder season, off season? e.g. February in Aspen is peak, August in Florida is off peak, etc.
    - (important) special requests made by guests, e.g. roses on arrival, baby crib, dog bed and bowls, etc.
    - surprising higher level trip theme, e.g. ancient Rome trip, surf trip, yoga retreat trip, wildlife trip, racing trip, jungle trip, desert trip, Art Basel trip, etc.
    - price category of hotel? e.g. "$$$$", "$$$", "$", "$", etc. Is it always hyper luxury "$$$$$"?
    - surprising amenities like surf spot beach front, private pool for each room, michelin dining, hot water springs, etc.
    - don't include obvious amenities like high speed wifi, TV, parking, etc.
    - unusual dining experiences e.g. michelin star, exclusively raw dining, etc.
    - specific hotel, e.g. Ritz-Carlton in Costa Rica, Four Seasons in Bali, etc.
    - hotel chains, keep specifics e.g. "Hilton", "Marriott", "Hyatt", "St. Regis", "Rosewood", "Relais & Chateaux", "Four Seasons", "Leading Hotels of the World", etc.
    - unusual type of hotel, e.g. villa only, cabin only, family only, adult only, romantic only, spa/wellness only, casino only, airport hotel only, business only, etc.
    - unusual hotel styles, e.g. historical, modern/contemporary, boutique, luxury, hyper-luxury, eco/green, surprising (e.g., treehouse rooms, igloos, etc.), themed (e.g., fantasy, movie, space) like Disney’s themed resorts, etc.
    - probable purpose of the trip: use the room type and number of guests to infer the purpose of the trip, e.g. business, family, couple, etc. 2 queen beds and 2 adults probably isn't a couple's getaway.
    - any other key insights that would be helpful for a travel planner to know.

    You're output should be a self-contained list of trip groups and their top 10 important, surprising, or repeating features. Each trip group should list all its
    trips, and each trip should list all its features (not just an addition to an existing list of trip groups, and not just an addition of trips to an existing trip group).

    Don't summarize by adding things like the following to your output:
    - "[**Original 7 trips (as previously listed) remain unchanged, now plus…**]" with no trips and no trip features
    - "Trip 16b20d83f41e0117 The Montcalm London Marble Arch, UK (Jun 29 to Jun 30 2019) [10 features as original]" with no trip features
    - "Weekend Ski Getaway #2 ’23 – 2023-01-27 to 01-28 (2 nights)" with no trip features
    Just relist everything from scratch everytime even if unchanged. If you need to save space, keep at least trip dates, trip hotel, trip location, and the
    3 most important features per trip, but don't cut more.

    Don't remove entire trip groups. Don't remove entire trips from trip groups.

    Return just list of the trip groups and their key information (as highlighted above).

    Here is the existing trip groups you have already started to generate:
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

def generate_trips_metadatas(trip_insights, num_trips, openai_api_key, progress_callback, progress=100) -> str:
    """
    Returns a list of trip information JSON objects.
    """

    if not openai_api_key:
        print("Warning: OPENAI_API_KEY environment variable not set. Skipping LLM keyword extraction.")
        return None
        
    # Define a prompt template for hotel characteristics
    prompt = f"""
    Based on the trip groups below, please recommend {num_trips} future trips as a json list of dictionaries like the one below.
    Please only return valid JSON and nothing else - no explanations or text before or after the JSON.
    Please only use the json fields that are present in the example trip json objects below - don't add extra json fields, add extra info in notes field for example.
    If you need to add more specifics, please add them to the notes field.

    Requirements:
    - Make sure the dates are in the future.
    - Recommend a trip to a region that the user has not gone to before but that they would like, e.g. since you like beach vacations, you'd like this other XYZ beach destination.
    - If you can't find a trip that is new but that the user would like, recommend a trip or event trip that was already completed many times (e.g. repeating yearly trip).
    - make sure to account for features in order of importance
    - only one type of trip, e.g. only one beach trip, one ski trip, one city trip, etc.
    - do your best to combine reasons based on previous trips on why the user would love the trip based on trip groups below. It needs to make sense, e.g. recommend a ski trip only if you saw a previous ski trip (if they don't know how to ski, they'll hate that recommendation), recommend a cultural trip if you saw a previous cultural trip, etc.
    - You should also have a reason for why you chose those dates (e.g. it's a school break for families, there is a popular event at that time in that location, etc.). Have at least 2 reasons per trip. Add reasons in the "reasons" field.
    
    Make sure to reason about number of and age of guests, e.g.
    - trips to special events like Coachella Music Festival, Cannes Film Festival, Art Basel Miami, Vancouver TED Conference, etc. are mostly for adults. If including children, make sure to account for the children's age and add reasons to go on trip for them too.
    - Cultural trips might be for families if user has children and a history of previous cultural family trips, or for adults if the user has a history of previous cultural adult trips.
    - Trips for families have to be during school holidays since families travel with children, e.g. Spring break, Christmas break, ski week, Summer break, etc.
    - Trips for adults would probably benefit from avoiding school holidays to avoid the crowds and high prices, but still be during peak or shoulder season for that location.

    Make sure to find and account for the following information in the trip json objects:
    - (super important) for location, is there something going on at that time of the year? e.g. Coachella Music Festival, Cannes Film Festival, Art Basel Miami, Vancouver TED Conference, etc.
    - (important) close in dates and location by car/train/airplane, e.g. Mar 24-28 2024 in Florence Italy and Mar 26-30 2024 in Pisa Italy, or Apr 14-18 2023 in Rome Italy and Apr 20-23 2023 in Paris France
    - (important) repeating in season, e.g. Thanksgiving trips, Summer trips, etc. 
    - (important) what is location known for and does hotel make it easy to do it? e.g. golfing in Scotland, skiing in Aspen, surfing in Bali, etc.
    - (important) for location, is it peak season, shoulder season, off season? e.g. February in Aspen is peak, August in Florida is off peak, etc.
    - (important) number and type of room (e.g. 1 room with king and 1 room with 2 queens, etc.), 2 room suite each with two queens, premium view (e.g. ocean view, city view, etc.), connecting rooms, 3+ room suite, 3+ room standalone villa, etc.
    - (important) special requests made by guests, e.g. roses on arrival, baby crib, dog bed and bowls, etc.
    - (important) number of and age of guests, adults, children, seniors, dogs or pets, etc.
    - surprising higher level trip theme, e.g. ancient Rome trip, surf trip, yoga retreat trip, wildlife trip, racing trip, jungle trip, desert trip, etc.
    - price category of hotel? e.g. "$$$$", "$$$", "$", "$", etc. Is it always hyper luxury "$$$$$"?
    - loyalty program, e.g. Marriott Bonvoy, Hilton Honors, etc.
    - payment method, e.g. loyalty points, gift cards, etc.
    - surprising amenities like surf spot beach front, private pool for each room, michelin dining, hot water springs, etc.
    - don't include obvious amenities like high speed wifi, TV, parking, etc.
    - unusual dining experiences e.g. michelin star, exclusively raw dining, etc.
    - specific hotel, e.g. Ritz-Carlton in Costa Rica, Four Seasons in Bali, etc.
    - hotel chains, keep specifics e.g. "Hilton", "Marriott", "Hyatt", "St. Regis", "Rosewood", "Relais & Chateaux", "Four Seasons", "Leading Hotels of the World", etc.
    - unusual type of hotel, e.g. villa only, cabin only, family only, adult only, romantic only, spa/wellness only, casino only, airport hotel only, business only, etc.
    - unusual hotel styles, e.g. historical, modern/contemporary, boutique, luxury, hyper-luxury, eco/green, surprising (e.g., treehouse rooms, igloos, etc.), themed (e.g., fantasy, movie, space) like Disney’s themed resorts, etc.
    - probable purpose of the trip: use the room type and number of guests to infer the purpose of the trip, e.g. business, family, couple, etc. 2 queen beds and 2 adults probably isn't a couple's getaway.
    - any other key insights that would be helpful for a travel planner to know.

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
            "reasons": "Multiple previous trips to Olympic Valley at peak season during ski week in February",
            "totalBudget": "$$$$",
            "purpose": "Family vacation"
        }}
    ]

    Here are the trip groups for the user that you have already generated, use these to ground your recommendations e.g.
    - don't recommend a ski trip if you don't see a ski trip below
    - don't recommend a music festival trip if you don't see a music festival trip below
    - don't recommend a trip for 4 people if you only see reservations for 2 people below
    - etc.
    Trip groups:
    {trip_insights}
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
