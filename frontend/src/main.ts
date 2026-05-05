import './style.css'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

// Fix Leaflet's default icon paths in Vite
import iconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png';
import iconUrl from 'leaflet/dist/images/marker-icon.png';
import shadowUrl from 'leaflet/dist/images/marker-shadow.png';

delete (L.Icon.Default.prototype as any)._getIconUrl;

L.Icon.Default.mergeOptions({
  iconRetinaUrl,
  iconUrl,
  shadowUrl,
});

interface Job {
  id: number;
  title: string;
  company: string;
  location: string;
  url: string;
  work_type: string;
  latitude: number | null;
  longitude: number | null;
}

// Restrict map to Australia bounds
const australiaBounds = L.latLngBounds(
  L.latLng(-55.0, 90.0), // South-West (expanded for padding)
  L.latLng(35.0, 175.0)  // North-East (expanded further North)
);

const map = L.map('map', {
  maxBounds: australiaBounds,
  maxBoundsViscosity: 1.0,
  minZoom: 4
}).setView([-25.2744, 133.7751], 4);

L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
  subdomains: 'abcd',
  maxZoom: 20
}).addTo(map);

const API_URL = 'http://localhost:8000/api/jobs/';

async function fetchJobs() {
  try {
    const response = await fetch(API_URL);
    if (!response.ok) throw new Error('Network response was not ok');
    const jobs: Job[] = await response.json();
    renderJobs(jobs);
  } catch (error) {
    console.error('Error fetching jobs:', error);
  }
}

function getBadgeClass(workType: string) {
  if (workType === 'remote') return 'badge-remote';
  if (workType === 'hybrid') return 'badge-hybrid';
  return 'badge-onsite';
}

function renderJobs(jobs: Job[]) {
  // Group jobs by their precise coordinates
  const locationGroups: Record<string, Job[]> = {};
  
  jobs.forEach(job => {
    if (job.latitude && job.longitude) {
      const key = `${job.latitude},${job.longitude}`;
      if (!locationGroups[key]) {
        locationGroups[key] = [];
      }
      locationGroups[key].push(job);
    }
  });

  // Create a single marker for each coordinate group
  Object.values(locationGroups).forEach(group => {
    const lat = group[0].latitude!;
    const lng = group[0].longitude!;
    const marker = L.marker([lat, lng]).addTo(map);
    
    // Generate popup HTML containing a list of all jobs at this location
    let popupHtml = `<div style="font-family: 'Inter', sans-serif;">`;
    
    if (group.length > 1) {
      popupHtml += `<h3 style="margin-top: 0; margin-bottom: 15px; border-bottom: 2px solid var(--accent-color, #646cff); padding-bottom: 5px;">${group.length} Jobs Here</h3>`;
    }
    
    group.forEach((job, index) => {
      // Add a subtle border between items if there are multiple
      const borderStyle = index < group.length - 1 ? 'border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 10px; margin-bottom: 10px;' : '';
      popupHtml += `
        <div style="${borderStyle}">
          <h4 style="margin:0 0 5px 0;">${job.title}</h4>
          <p style="margin:5px 0;"><strong>${job.company}</strong></p>
          <span class="badge ${getBadgeClass(job.work_type)}">${job.work_type}</span>
          <br>
          ${job.url ? `<a href="${job.url}" target="_blank" style="display:inline-block; margin-top:8px;">View Job</a>` : ''}
        </div>
      `;
    });
    
    popupHtml += `</div>`;
    // Use Leaflet's native maxHeight option to handle scrolling properly, which prevents it from being cut off
    marker.bindPopup(popupHtml, { minWidth: 250, maxHeight: 300, autoPanPadding: [20, 20] });
  });
}

// Initial fetch
fetchJobs();
