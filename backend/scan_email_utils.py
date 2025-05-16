from flask import Flask
from flask import request, session, redirect
# from flask_cors import CORS

import os
import json
import traceback
import base64
import re
from html import unescape

from threading import Lock
import concurrent.futures

from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as google_auth_requests
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.http import HttpError

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from groq import Groq

from dotenv import load_dotenv


# Load environment variables
load_dotenv()

# Gmail API configuration
# If you need additional scopes, add them here
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid"
]
CLIENT_ID = os.getenv('GOOGLE_CLOUD_GMAIL_CLIENT_ID')
CLIENT_SECRET = os.getenv('GOOGLE_CLOUD_GMAIL_CLIENT_SECRET')
FLASK_KEY = os.getenv('FLASK_KEY')
REDIRECT_URI = os.getenv('REDIRECT_URI')
LOGGED_IN_REDIRECT_URI = os.getenv('LOGGED_IN_REDIRECT_URI')
MAX_CONCURRENCY = 20
NUM_TRIPS_METADATA_TO_GENERATE = 5

def load_jsonl(file_path):
    with open(file_path, 'r') as f:
        return [json.loads(line) for line in f]

hotel_reservation_search_keywords = load_jsonl('hotel_reservation_search_keywords.jsonl')
hotel_reservation_search_keywords = [f'"{keyword}"' for keyword in hotel_reservation_search_keywords]
HOTEL_RESERVATION_SEARCH_QUERY = ' OR '.join(hotel_reservation_search_keywords)

app = Flask(__name__)
#setting app secret key
app.secret_key = FLASK_KEY

# # Enable CORS for all routes
# CORS(app)

# FOR NON_PROD ONLY! Setting OAUTHLIB insecure transport to 1 (needed for development with self-signed certificates)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'



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
            include_granted_scopes="true"
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
        id_token=credentials._id_token
        ,request=google_auth_requests.Request()
        ,audience=CLIENT_ID
    )
    
    # Set the user information to an element of the session.
    # TODO: Do something else with this (login, store in JWT, etc)
    session["id_info"] = id_info
    session["oauth_state"] = state
    
    #redirecting to the final redirect (i.e., logged in page)
    logged_in_redirect_response = LOGGED_IN_REDIRECT_URI

    return logged_in_redirect_response

def get_gmail_service_from_session(session):
    """Get authenticated Gmail service."""

    # Retrieve credentials from session
    if 'credentials' not in session:
        raise Exception("No credentials found in session. Please try logging in again.")
    
    # Rebuild credentials object and build Gmail service
    credentials = Credentials(**session['credentials'])
    gmail_service = build('gmail', 'v1', credentials=credentials)

    return gmail_service

def scan_email(progress_callback):
    # # Retrieve User data if needed:
    # name = session["id_info"]["name"]
    # picture = session["id_info"]["picture"]
    # email = session["id_info"]["email"]

    # Retrieve credentials from session
    gmail_service = get_gmail_service_from_session(session)

    yield from progress_callback("Searching for emails...", 5)
    messages = yield from search_emails(
        gmail_service,
        HOTEL_RESERVATION_SEARCH_QUERY,
        progress_callback,
        progress=5,
        max_results=5000
    )
    if not messages or len(messages) == 0:
        raise Exception("No emails found")
    
    email_count = len(messages)
    yield from progress_callback(f"Found {email_count} emails", 10)

    yield from progress_callback("Getting metadata for emails...", 15)
    msg_ids = [message['id'] for message in messages]
    email_metadatas = yield from get_email_metadatas_batch(msg_ids, progress_callback, progress=15)

    yield from progress_callback("Filtering emails based on reply to...", 20)
    email_metadatas = [email_metadata for email_metadata in email_metadatas if "Unknown" in email_metadata['in_reply_to']]
    yield from progress_callback(f"Filtered down to {len(email_metadatas)} by removing emails that are replies to another email in the same thread.", 20)
    

    yield from progress_callback("Filtering emails based on title...", 25)
    prompts = {
        email_metadata['id']: f"Here is metadata for an email, is it a hotel reservation confirmation? Just"
                               "answer True or False and nothing else. Metadata: {email_metadata}"
        for email_metadata in email_metadatas
    }
    batch_hotel_reservation_classification = yield from run_groq_inference_batch_with_pool(prompts, progress_callback, progress=30)
    hotel_reservation_emails = [
        email_metadata
        for email_metadata in email_metadatas
        if "True" == batch_hotel_reservation_classification.get(email_metadata['id'], 'False')
    ]
    yield from progress_callback(f"Filtered down to {len(hotel_reservation_emails)} based on title.", 35)

    yield from progress_callback("Getting full content of emails...", 40)
    msg_ids = [message['id'] for message in hotel_reservation_emails]
    full_hotel_reservation_emails = yield from get_full_email_batch(msg_ids, progress_callback, progress=40)

    yield from progress_callback("Filtering emails based on body...", 45)
    prompts = {
        email_metadata['id']: f"Here is data for an email, is it a hotel reservation confirmation? Make sure to only keep hotel reservations (and filter out restaurant reservations and other travel related emails). Just answer True or False and nothing else. Metadata: {email_metadata}"
        for email_metadata in full_hotel_reservation_emails
    }
    # batch_hotel_reservation_classification_full_email = batch_llm_calls(prompts)
    batch_hotel_reservation_classification_full_email = yield from run_groq_inference_batch_with_pool(prompts, progress_callback, progress=45)
    body_checked_filtered_hotel_reservation_emails = [
        email_metadata
        for email_metadata in full_hotel_reservation_emails
        if "True" == batch_hotel_reservation_classification_full_email.get(email_metadata['id'], 'False')
    ]
    yield from progress_callback(f"Filtered down to {len(body_checked_filtered_hotel_reservation_emails)} based on body.", 50)

    yield from progress_callback(f"Getting key insights from each email...", 55)
    prompts = {
        email_metadata['id']: f""""
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
        for email_metadata in body_checked_filtered_hotel_reservation_emails
    }
    batch_hotel_reservation_key_insights = yield from run_groq_inference_batch_with_pool(prompts, progress_callback, progress=55)
    hotel_reservation_key_insights = [
        {
            **email_metadata,
            'key_insights': batch_hotel_reservation_key_insights.get(email_metadata['id'], '')
        }
        for email_metadata in body_checked_filtered_hotel_reservation_emails
    ]
    yield from progress_callback(f"Completed getting key insights from each email...", 60)

    yield from progress_callback(f"Generating insights from all emails...", 75)
    trip_insights = yield from generate_trip_insights(hotel_reservation_key_insights, os.getenv("OPENAI_API_KEY"), progress_callback, progress=80, existing_trip_insights = "")
    yield from progress_callback(f"Completed generating insights from all emails...", 85)
    print(f"\ntrip_insights:\n{trip_insights}\n")

    yield from progress_callback(f"Generating up to {NUM_TRIPS_METADATA_TO_GENERATE} trip metadatas...", 95)    
    # hotel_reservation_key_insights # If too much data for context window, just send summarized trip_insights, works pretty well.
    trip_jsons = yield from generate_trips_metadatas([], trip_insights, NUM_TRIPS_METADATA_TO_GENERATE, os.getenv("OPENAI_API_KEY"), progress_callback, progress=100)
    yield from progress_callback(f"Completed generating up to {NUM_TRIPS_METADATA_TO_GENERATE} trip metadatas...", 100)
    # Pretty print the trip JSON data
    if trip_jsons:
        print("\n=== Generated Trip Metadata ===\n")
        print(json.dumps(trip_jsons, indent=4))
        print("\n=============================\n")

    return trip_insights, trip_jsons


def search_emails(service, query, progress_callback, progress=5, max_results=500):
    """Search for emails matching the query.
    
    Args:
        service: Authenticated Gmail API service instance.
        query: String used to filter messages matching specific criteria.
        max_results: Maximum number of results to return (default 500)
        
    Returns:
        List of messages that match the criteria
    """
    yield from progress_callback(f"search_emails...", progress)
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
            yield from progress_callback(f"Retrieved {len(messages)} emails IDs of max {max_results}...", progress)
            
            # Check if we've reached the desired number of results
            if len(messages) >= max_results:
                yield from progress_callback(f"Reached maximum of {max_results} emails", progress)
                break
                
            # Get token for next page or exit if no more pages
            next_page_token = result.get('nextPageToken')
            if not next_page_token:
                break
        
        return messages
        
    except Exception as error:
        yield from progress_callback(f"An error occurred: {error}\nstack_trace: {traceback.format_exc()}", progress)
        return []

def get_email_metadatas_batch(msg_ids, progress_callback, progress=15):
    """Get email metadata for multiple message IDs in a batch request."""
    results = []
    results_lock = Lock()
    
    def fetch_single_message(msg_id, idx, len_emails):
        """Process a single message and return its metadata."""
        try:
            service = get_gmail_service_from_session(session)

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
                if fetched_count % 10 == 0:
                    yield from progress_callback(f"Fetched {fetched_count} / {len_emails} email metadatas...", progress)
            
            return email_metadata
        
        except HttpError as error:
            yield from progress_callback(f"Error fetching message {msg_id}: {error}", progress)
            return None
    
    # results = [fetch_single_message(msg_id, idx) for idx, msg_id in enumerate(msg_ids)]

    # Create a thread pool with limited concurrency
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as executor:
        # Submit all tasks to the executor
        len_emails = len(msg_ids)
        futures = {executor.submit(fetch_single_message, msg_id, idx, len_emails): msg_id for idx, msg_id in enumerate(msg_ids)}
        
        # Process results as they complete (optional)
        for future in concurrent.futures.as_completed(futures):
            msg_id = futures[future]
            try:
                # This will re-raise any exceptions from the task
                yield from future.result()
            except Exception as exc:
                yield from progress_callback(f"Message {msg_id} generated an exception: {exc}", progress)
    
    return results

def run_groq_inference(prompt, model):
    groq_client = Groq()
    completion = groq_client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": prompt
            },
        ],
        temperature=0.6,
        max_completion_tokens=128,
        top_p=1.0,
        stream=False,
        stop=None,
    )
    return completion.choices[0].message.content

def run_groq_inference_batch_with_pool(
    prompts_dict,
    progress_callback,
    progress=20,
    max_workers=MAX_CONCURRENCY,
    model="meta-llama/llama-4-maverick-17b-128e-instruct",
    ):
    """Process multiple prompts with Groq API using a thread pool."""
    # Also smaller "meta-llama/llama-4-scout-17b-16e-instruct" 
    results = {}
    results_lock = Lock() # To safely update the shared results dictionary
    completed_count = 0
    total_prompts = len(prompts_dict)

    def process_single_prompt(prompt_id, prompt_text):
        nonlocal completed_count
        try:
            response = run_groq_inference(prompt_text, model=model) # Your existing inference function
            with results_lock:
                results[prompt_id] = response
                completed_count += 1
                if completed_count % 10 == 0:
                    yield from progress_callback(f"Completed {completed_count} / {total_prompts}", progress)
            return prompt_id, response
        except Exception as e:
            with results_lock:
                results[prompt_id] = f"ERROR: {str(e)}"
                completed_count += 1
                yield from progress_callback(f"Error processing prompt ID {prompt_id}: {e}. Completed {completed_count} / {total_prompts}.", progress)
            return prompt_id, f"ERROR: {str(e)}"

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit tasks: executor.submit(function, arg1, arg2, ...)
        future_to_prompt_id = {executor.submit(process_single_prompt, pid, ptext): pid for pid, ptext in prompts_dict.items()}

        for future in concurrent.futures.as_completed(future_to_prompt_id):
            prompt_id_completed = future_to_prompt_id[future]
            try:
                yield from future.result()
            except Exception as exc:
                yield from progress_callback(f'Prompt ID {prompt_id_completed} generated an exception in future: {exc}', progress)
                with results_lock:
                    if prompt_id_completed not in results:
                         results[prompt_id_completed] = f"ERROR: {str(exc)}"

    return results

def get_full_email_batch(
    msg_ids,
    progress_callback,
    progress=20,
    ):
    """Get full email for multiple message IDs in a batch request."""
    results = []
    results_lock = Lock()
    
    def fetch_single_full_message(msg_id, idx, len_emails):
        """Process a single message and return its metadata."""
        try:
            gmail_service = get_gmail_service_from_session(session)

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
                results.append(email_metadata)
                fetched_count = len(results)            
                if fetched_count % 10 == 0:
                    yield from progress_callback(f"Fetched {fetched_count} / {len_emails} full email contents...", progress)
            
            return email_metadata
        
        except HttpError as error:
            yield from progress_callback(f"Error fetching message {msg_id}: {error}", progress)
            return None
    
    # results = [fetch_single_full_message(msg_id, idx) for idx, msg_id in enumerate(msg_ids[:10])]

    # Create a thread pool with limited concurrency
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as executor:
        # Submit all tasks to the executor
        len_emails = len(msg_ids)
        futures = {executor.submit(fetch_single_full_message, msg_id, idx, len_emails): msg_id for idx, msg_id in enumerate(msg_ids)}
        
        # Process results as they complete (optional)
        for future in concurrent.futures.as_completed(futures):
            msg_id = futures[future]
            try:
                # This will re-raise any exceptions from the task
                yield from future.result()
            except Exception as exc:
                yield from progress_callback(f"Message {msg_id} generated an exception: {exc}", progress)
    
    return results

def generate_trip_insights(trip_message_datas, openai_api_key, progress_callback, progress=65, existing_trip_insights = "") -> str:
    """
    Returns a list of trip information JSON objects.
    """

    if not openai_api_key:
        print("Warning: OPENAI_API_KEY environment variable not set. Skipping LLM keyword extraction.")
        return None
    
    try:        
        llm_model = "o4-mini"
        
        # Initialize the LLM with the API key explicitly
        llm = ChatOpenAI(model=llm_model, openai_api_key=openai_api_key)
        
        # Define a prompt template for hotel characteristics
        template = """
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
        
        prompt = ChatPromptTemplate.from_template(template)
        
        # Generate the response
        chain = prompt | llm
        response = chain.invoke({
            "existing_trip_insights": existing_trip_insights,
            "trip_message_datas": trip_message_datas
        })

        # Extract JSON from the response
        response_content = response.content
        if not response_content:
            yield from progress_callback(f"LLM did not return a response to generate trip insights", progress)
            return None
        
        return response_content
            
    except ImportError:
        yield from progress_callback(f"LangChain or OpenAI packages not installed.", progress)
        return None

def generate_trips_metadatas(trip_message_datas, trip_insights, num_trips, openai_api_key, progress_callback, progress=100) -> str:
    """
    Returns a list of trip information JSON objects.
    """

    if not openai_api_key:
        print("Warning: OPENAI_API_KEY environment variable not set. Skipping LLM keyword extraction.")
        return None
    
    try:        
        llm_model = "o4-mini"  # Reasoning capabilities are important for this task (e.g. "2 Queen beds probably isn't a couple's getaway purpose trip.")
        
        # Initialize the LLM with the API key explicitly
        llm = ChatOpenAI(model=llm_model, openai_api_key=openai_api_key)
        
        # Define a prompt template for hotel characteristics
        template = """
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
        
        prompt = ChatPromptTemplate.from_template(template)
        
        # Generate the response
        chain = prompt | llm
        response = chain.invoke({
            "trip_message_datas": trip_message_datas,
            "trip_insights": trip_insights,
            "num_trips": num_trips
        })

        # Extract JSON from the response
        response_content = response.content
        if not response_content:
            yield from progress_callback(f"LLM did not return a response to generate trip metadata", progress)
            return None
        
        # Try to parse the response as JSON
        try:
            # Parse the JSON
            trip_jsons = json.loads(response_content)
            return trip_jsons
        except json.JSONDecodeError as e:
            yield from progress_callback(f"Error parsing JSON response: {e} Raw response: {response_content}", progress)
            return None
            
    except ImportError:
        yield from progress_callback(f"LangChain or OpenAI packages not installed.", progress)
        return None