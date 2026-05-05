import os
import time
import requests
from dotenv import load_dotenv
from django.core.management.base import BaseCommand
from geopy.geocoders import Nominatim
from jobs.models import Job

class Command(BaseCommand):
    help = 'Fetches IT jobs from Adzuna API using specific keywords and geocodes their locations'

    def handle(self, *args, **kwargs):
        load_dotenv()
        app_id = os.getenv('ADZUNA_APP_ID')
        app_key = os.getenv('ADZUNA_APP_KEY')
        
        if not app_id or not app_key:
            self.stdout.write(self.style.ERROR("Adzuna API credentials not found in .env. Exiting."))
            return
            
        self.stdout.write("Starting Adzuna API fetcher...")
        
        scraped_data = self.fetch_jobs(app_id, app_key)
        
        if not scraped_data:
            self.stdout.write(self.style.WARNING("No jobs fetched."))
            return

        # Save to DB
        geolocator = Nominatim(user_agent="django_job_tracker_123")
        
        added_jobs_count = 0
        added_companies = set()
        skipped_count = 0
        
        for data in scraped_data:
            # Check duplicates
            if Job.objects.filter(url=data['url']).exists() and data['url']:
                skipped_count += 1
                continue
            if Job.objects.filter(title=data['title'], company=data['company']).exists():
                skipped_count += 1
                continue

            lat = data.get('latitude')
            lng = data.get('longitude')

            if lat is None or lng is None:
                search_query = f"{data['company']} {data['location']}"
                self.stdout.write(f"Geocoding missing coordinates for: {search_query}")
                try:
                    time.sleep(1) # Rate limit protection for Nominatim
                    loc = geolocator.geocode(search_query)
                    if loc:
                        lat, lng = loc.latitude, loc.longitude
                    else:
                        time.sleep(1)
                        # Fallback to just searching the location string
                        loc = geolocator.geocode(data['location'])
                        if loc:
                            lat, lng = loc.latitude, loc.longitude
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"Geocoding failed for {data['company']}: {e}"))
            else:
                self.stdout.write(f"Using native Adzuna coordinates for: {data['title']} at {data['company']}")
                
            Job.objects.create(
                title=data['title'],
                company=data['company'],
                location=data['location'],
                url=data['url'],
                work_type=data['work_type'],
                latitude=lat,
                longitude=lng
            )
            added_jobs_count += 1
            added_companies.add(data['company'])

        self.stdout.write(self.style.SUCCESS(
            f"Scraping completed! Added {added_jobs_count} unique positions from {len(added_companies)} unique companies. Skipped {skipped_count} duplicates."
        ))

    def fetch_jobs(self, app_id, app_key):
        jobs_data = []
        queries = [
            'software developer', 
            'software engineer', 
            'full stack developer', 
            'data science', 
            'devops engineer'
        ]
        
        for query in queries:
            self.stdout.write(f"Fetching jobs for keyword: '{query}'...")
            # Using the 'au' endpoint specifically to guarantee Australian jobs
            url = f"https://api.adzuna.com/v1/api/jobs/au/search/1"
            params = {
                'app_id': app_id,
                'app_key': app_key,
                'results_per_page': 50,
                'what': query
            }
            
            try:
                response = requests.get(url, params=params, timeout=15)
                response.raise_for_status()
                data = response.json()
                
                jobs = data.get('results', [])
                self.stdout.write(f"Found {len(jobs)} jobs for '{query}'.")
                
                for job in jobs:
                    title = job.get('title', '')
                    company = job.get('company', {}).get('display_name', '')
                    location = job.get('location', {}).get('display_name', 'Australia')
                    redirect_url = job.get('redirect_url', '')
                    
                    # Adzuna natively provides coordinates for most jobs!
                    latitude = job.get('latitude')
                    longitude = job.get('longitude')
                    
                    # Work type logic
                    description = job.get('description', '').lower()
                    title_lower = title.lower()
                    work_type = 'onsite'
                    if 'remote' in title_lower or 'remote' in description or 'work from home' in description:
                        work_type = 'remote'
                    elif 'hybrid' in title_lower or 'hybrid' in description:
                        work_type = 'hybrid'
                        
                    jobs_data.append({
                        'title': title,
                        'company': company,
                        'location': location,
                        'url': redirect_url,
                        'work_type': work_type,
                        'latitude': latitude,
                        'longitude': longitude
                    })
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"API fetch error for '{query}': {e}"))
                
        return jobs_data
