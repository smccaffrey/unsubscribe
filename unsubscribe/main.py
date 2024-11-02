import re
import requests

from typing import Dict, List, Optional, Tuple, Union
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
from googleapiclient.discovery import build, Resource  # type: ignore
import tldextract  # type: ignore

# If modifying these SCOPES, delete the token.json file
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

ALLOWLIST = [
    'linkedin.com', 
    'medium.com', 
    'onemedical.com', 
    'circleci.com', 
]

def authenticate_gmail() -> Resource:
    """Authenticate and create a Gmail API service instance."""
    # creds: Optional[Credentials]
    # The file token.json stores the user's access and refresh tokens, and is created automatically when the authorization flow completes for the first time
    try:
        creds: Credentials = Credentials.from_authorized_user_file('token.json', SCOPES)  # type: ignore
    
    except Exception as e:
        print(e)
        flow: InstalledAppFlow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)  # type: ignore
        creds: Credentials = flow.run_local_server(port=0)  # type: ignore
        # Save the credentials for future use
        with open('token.json', 'w') as token:
            token.write(creds.to_json())  # type: ignore
    
    return_service: Resource = build('gmail', 'v1', credentials=creds)

    return return_service

def get_unsubscribe_links_from_message(message: Union[Dict[str, object], None]) -> List[str]:

    """Extract unsubscribe links from the email message."""
    unsubscribe_links: List[str] = []
    
    # Ensure message is a dictionary
    if not isinstance(message, dict):
        return unsubscribe_links

    # Attempt to get 'payload' and ensure it's a dictionary
    payload = message.get('payload', {})
    if not isinstance(payload, dict):
        payload = {}

    # Attempt to get headers
    headers: List[Dict[str, str]] = payload.get('headers', [])

    # Check for List-Unsubscribe header
    for header in headers:
        if header.get('name') == 'List-Unsubscribe':
            links: List[str] = re.findall(r'<(http[s]?://[^>]+)>', header.get('value', ''))
            unsubscribe_links.extend(links)
    
    # Check in the message body
    for part in payload.get('parts', []):
        try:
            if part.get('mimeType') in ['text/plain', 'text/html']:
                body_data: Optional[str] = part.get('body', {}).get('data')
                if body_data:
                    # Decode and find URLs that include 'unsubscribe'
                    decoded_body: str = body_data.encode('utf-8').decode('utf-8')
                    links = re.findall(r'(https?://\S+)', decoded_body)
                    unsubscribe_links.extend([link for link in links if "unsubscribe" in link.lower()])
        except Exception as e:
            print(f"Error parsing part: {e}")

    return unsubscribe_links

def fetch_first_n_emails(service: Resource, n: int = 50) -> List[Tuple[str, str]]:
    """Fetch the first N emails from the Gmail account."""
    unsubscribe_links: List[str] = []
    try:
        # Get the list of messages
        results: dict = service.users().messages().list(userId='me', maxResults=n).execute()  # type: ignore
        messages: List[dict] = results.get('messages', [])  # type: ignore
        
        if not messages:
            print('No emails found.')
            return [], []

        total: int = len(messages)
        for index, message in enumerate(messages, start=1):
            msg_id: str = message['id']
            msg: dict = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
            subject: str = next((header['value'] for header in msg['payload']['headers'] if header['name'] == 'Subject'), 'No Subject')
            
            # Update the counter in place
            print(f"\r{' ' * 100}", end='')  # Clear the line by overwriting with spaces
            print(f"\rProcessing email {index}/{total}", end='')

            # Extract unsubscribe links
            links: List[str] = get_unsubscribe_links_from_message(msg)
            # print(links)

            if links:
                unsubscribe_links.extend(links)
        
        # print()  # Move to the next line after processing

    except Exception as e:
        print(f"\nAn error occurred: {e}")

    response: List[Tuple[str, str]] = [(tldextract.extract(link).registered_domain, link) for link in unsubscribe_links]

    return response

if __name__ == '__main__':
    
    # Authticate to Gmail API
    service: Resource = authenticate_gmail()
    print("Successfully authenticated ...")

    # Fetch n most recent emails
    unsubscribe_links = fetch_first_n_emails(service, n=100)
    
    print(f"Unsubscribe Links Found: {len(unsubscribe_links)}")

    # Unsubscribe but not from ALLOWLIST
    for parent_domain, unsubscribe_link in unsubscribe_links:
        
        if parent_domain not in ALLOWLIST:
            unsubscribe_response = requests.get(
                url=unsubscribe_link,
                timeout=3
            )
            print(f"Successfull unsubscribed from: {parent_domain} \t\t\t {unsubscribe_response.status_code}")

    # Write results to csv file for examination
    # unique_parent_domains = set([link for _,link in response])
    # with open(
    #     file="unsubscribe_links.csv",
    #     mode="w",
    #     encoding="utf-8",
    #     newline="\n",
    # ) as file:
    #     writer = csv.writer(file)

    #     for parent_domain, unsubscribe_link in unsubscribe_links:
    #         writer.writerow([parent_domain, unsubscribe_link])