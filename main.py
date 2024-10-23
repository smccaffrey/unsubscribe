from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import re

# If modifying these SCOPES, delete the token.json file
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def authenticate_gmail():
    """Authenticate and create a Gmail API service instance."""
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is created automatically when the authorization flow completes for the first time
    try:
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    except Exception:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        # Save the credentials for future use
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def get_unsubscribe_links_from_message(message):
    """Extract unsubscribe links from the email message."""
    unsubscribe_links = []
    payload = message.get('payload', {})
    headers = payload.get('headers', [])

    # Check for List-Unsubscribe header
    for header in headers:
        if header.get('name') == 'List-Unsubscribe':
            links = re.findall(r'<(http[s]?://[^>]+)>', header.get('value'))
            unsubscribe_links.extend(links)
    
    # Check in the message body
    for part in payload.get('parts', []):
        try:
            if part.get('mimeType') in ['text/plain', 'text/html']:
                body_data = part.get('body', {}).get('data')
                if body_data:
                    # Decode and find URLs that include 'unsubscribe'
                    decoded_body = body_data.encode('utf-8').decode('utf-8')
                    links = re.findall(r'(https?://\S+)', decoded_body)
                    unsubscribe_links.extend([link for link in links if "unsubscribe" in link.lower()])
        except Exception as e:
            print(f"Error parsing part: {e}")

    return unsubscribe_links

def fetch_first_n_emails(service, n=50):
    """Fetch the first N emails from the Gmail account."""
    unsubscribe_links = []
    try:
        # Get the list of messages
        results = service.users().messages().list(userId='me', maxResults=n).execute()
        messages = results.get('messages', [])
        
        if not messages:
            print('No emails found.')
            return []

        total = len(messages)
        for index, message in enumerate(messages, start=1):
            msg_id = message['id']
            msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
            subject = next((header['value'] for header in msg['payload']['headers'] if header['name'] == 'Subject'), 'No Subject')
            
            # Update the counter in place
            print(f"\r{' ' * 100}", end='')  # Clear the line by overwriting with spaces
            print(f"\rProcessing email {index}/{total}: {subject[:100]}", end='')

            # Extract unsubscribe links
            links = get_unsubscribe_links_from_message(msg)
            if links:
                unsubscribe_links.extend(links)
        
        print()  # Move to the next line after processing

    except Exception as e:
        print(f"\nAn error occurred: {e}")

    
    return messages, unsubscribe_links

if __name__ == '__main__':
    service = authenticate_gmail()
    print("Successfull authenticated ...")
    messages, unsubscribe_links = fetch_first_n_emails(service, n=50)
    print(f"Emails ingested: {len(messages)}")
    print(f"Unsubscribe Links Found: {len(unsubscribe_links)}")
    # for link in unsubscribe_links:
    #     print(link)
