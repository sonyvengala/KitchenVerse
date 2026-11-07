# Google Maps Platform Integration Guide
**Application:** KitchenVerse

This document provides step-by-step instructions to configure Google Maps Platform APIs for KitchenVerse across kitchen location selection, customer delivery address search, and geographic proximity calculations.

---

## 1. Create or Select a Google Cloud Project

1. Navigate to the [Google Cloud Console](https://console.cloud.google.com/).
2. In the top project dropdown, click **New Project**.
3. Name your project (e.g., `CloudKitchen-Production` or `CloudKitchen-Dev`) and click **Create**.
4. Make sure your newly created project is selected in the project bar.

---

## 2. Enable Billing

Google Maps Platform requires an active billing account linked to the project:
1. Go to **Billing** in the Google Cloud Console navigation menu.
2. Link your Cloud Billing account to the project.
> **Note:** Google provides a recurring $200 monthly free tier credit across Maps, Routes, and Places, which is sufficient for extensive development and testing.

---

## 3. Enable Required APIs

In the **APIs & Services > Library** menu, search for and enable each of the following:

1. **Maps JavaScript API**
   - Renders interactive maps (`AdvancedMarkerElement`, custom map styling, kitchen coordinate mapping).
2. **Places API**
   - Legacy places support and text search.
3. **Places API (New)**
   - High-performance place autocomplete suggestions (`Kondapur`, `Jubilee Hills`, etc.) and place details.
4. **Geocoding API**
   - Reverse-geocodes browser geolocation latitude/longitude coordinates into formatted physical addresses.
5. **Distance Matrix API** *(Optional)*
   - For road-network driving distance/ETA calculations between kitchen hubs and customer dropoff points.

---

## 4. Generate and Restrict API Keys

### Step 4.1: Create an API Key
1. Go to **APIs & Services > Credentials**.
2. Click **+ Create Credentials > API Key**.
3. Copy your generated API key.

### Step 4.2: Apply HTTP Referrer Restrictions (Frontend Client Key)
To prevent unauthorized quota consumption, restrict your browser key:
1. Click on the created API key to edit its settings.
2. Under **Application restrictions**, select **Websites (HTTP referrers)**.
3. Add the following website restrictions:
   - Development:
     - `http://localhost:5173/*`
     - `http://localhost:3000/*`
     - `http://127.0.0.1:5173/*`
   - Production (Replace with your actual domain):
     - `https://yourdomain.com/*`
     - `https://*.yourdomain.com/*`

### Step 4.3: Apply API Restrictions
1. Under **API restrictions**, select **Restrict key**.
2. Select only the necessary APIs:
   - Maps JavaScript API
   - Places API
   - Places API (New)
   - Geocoding API
3. Click **Save**.

---

## 5. Environment Variable Configuration

Add the API key to your local `.env` file (or CI/CD secrets):

```env
# Frontend Client Key (Vite embeds this in client bundles)
VITE_GOOGLE_MAPS_API_KEY=AIzaSyYourGeneratedMapsApiKeyHere

# Backend Service Key (Optional if backend geocoding is used)
GOOGLE_MAPS_API_KEY=AIzaSyYourGeneratedMapsApiKeyHere
```

> **Security Warning:**
> NEVER commit `.env` or your actual Google Cloud API key into Git repository commits. Keep keys strictly in `.env` (which is included in `.gitignore`).

---

## 6. Graceful Fallback Behavior

If `VITE_GOOGLE_MAPS_API_KEY` is omitted or left empty:
- The CloudKitchen application loads completely without crashing or blank screens.
- Kitchen Owner Settings displays:
  `"Google Maps is not configured. Add VITE_GOOGLE_MAPS_API_KEY to enable maps."`
  along with an interactive Leaflet/OSM map picker and manual coordinate fields.
- Customer Delivery Location picker allows entering addresses and using browser geolocation (`navigator.geolocation`).
- Haversine Great-Circle distance formula calculates exact geographic distances in kilometers without requiring paid external APIs.

---

## 7. Compliance and Data Integrity Rules

1. **Google Maps data is NOT CloudKitchen business data.**
   Places returned from Google Places searches must never automatically become CloudKitchen database records (kitchens, menu items, orders, or inventory).
2. **External Places Attribution:**
   When customers opt into viewing "Google Places (External restaurants)", external establishments are clearly labeled and disclaimed as external entities that cannot receive CloudKitchen orders.
