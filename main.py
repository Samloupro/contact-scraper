import asyncio
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
import uuid
import logging
from urllib.parse import urlparse
from utils.email_extractor import extract_emails_html, extract_emails_jsonld
from utils.phone_extractor import extract_phones_html, extract_phones_jsonld, validate_phones
from utils.social_links import extract_social_links  # Updated import statement
from utils.link_scraper import link_scraper, extract_links, is_valid_url
from utils.user_agent import get_user_agent_headers  # Ensure this import is present
from utils.link_analyzer import analyze_links
import requests

app = Flask(__name__)
SCRIPT_VERSION = "V 1.8 / Social link "

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def analyze_links_parallel(links, headers, domain):
    valid_links = [link for link in links if is_valid_url(link)]
    with ThreadPoolExecutor() as executor:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        tasks = [
            loop.run_in_executor(executor, analyze_links, link, headers, domain)
            for link in valid_links
        ]
        results = loop.run_until_complete(asyncio.gather(*tasks))
    return results

@app.route('/scrape', methods=['GET'])
def scrape():
    url = request.args.get('url')
    headers = get_user_agent_headers()

    include_emails = request.args.get('include_emails', 'true').lower() == 'true'
    include_phones = request.args.get('include_phones', 'true').lower() == 'true'
    include_social_links = request.args.get('include_social_links', 'true').lower() == 'true'
    include_unique_links = request.args.get('include_unique_links', 'true').lower() == 'true'
    
    max_link = request.args.get('max_link')  # Get the max_link parameter from the query string
    max_link = int(max_link) if max_link else None

    links, error = link_scraper(url, headers, max_link)
    if error:
        return jsonify({'error': error}), 500

    domain = urlparse(url).netloc

    emails, phones, visited_links = {}, {}, set()
    if include_unique_links and not (include_emails or include_phones or include_social_links):
        valid_links = [link for link in links if is_valid_url(link)]
        visited_links.update(valid_links)
    else:
        if include_emails or include_phones or include_unique_links:
            results = analyze_links_parallel(links, headers, domain)
            for result in results:
                emails.update(result[0])
                phones.update(result[1])
                visited_links.update(result[2])

        social_links = {}
        if include_social_links:
            social_links = extract_social_links(visited_links)  # Updated function call

    result = {
        "request_id": str(uuid.uuid4()),
        "domain": url.split("//")[-1].split("/")[0],
        "query": url,
        "status": "OK",
        "data": [
            {
                "emails": [{"value": email, "sources": sources} for email, sources in emails.items()] if include_emails else [],
                "phone_numbers": [{"value": phone, "sources": sources} for phone, sources in phones.items()] if include_phones else [],
                "social_links": social_links if include_social_links else {},
                "unique_links": sorted(list(visited_links)) if include_unique_links else []
            }
        ]
    }

    logger.info(f"Processed URL: {url}")
    return jsonify(result)

if __name__ == '__main__':
    print(f"Starting script version: {SCRIPT_VERSION}")
    app.run(host='0.0.0.0', port=5000)
    print("Application is running at http://<your-domain-or-ip>:5000")
