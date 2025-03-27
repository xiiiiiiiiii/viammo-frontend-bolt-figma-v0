import axios from 'axios';
import { Trip, TripCalendarItem } from './types';

// API base URL - when using the Vite proxy, we can simply use '/api'
// This will be proxied to http://localhost:5001/api through the Vite dev server
const API_BASE_URL = '/api';

// API functions for MongoDB operations
export const api = {
  // Fetch all trips from MongoDB
  getTrips: async (): Promise<Trip[]> => {
    try {
      console.log('Fetching trips from API server...');
      
      // Try to fetch from API server
      const response = await axios.get(`${API_BASE_URL}/trips`);
      console.log('API response:', response.data);
      
      if (response.data && Array.isArray(response.data)) {
        return response.data;
      }
      
      throw new Error('Invalid response from API server');
    } catch (error) {
      console.error('Error fetching trips from API server:', error);
      // Return empty array with error
      throw new Error('Failed to fetch trips. Please ensure the API server is running and connected to MongoDB.');
    }
  },
  
  // Check API server health
  checkApiHealth: async (): Promise<{ status: string; message: string }> => {
    console.log('API server: ', API_BASE_URL);
    try {
      // Try the API health endpoint to see if server is running
      const response = await axios.get(`${API_BASE_URL}/health`);
      console.log('API server health check:', response.data);
      return { 
        status: 'ok', 
        message: 'API server is running correctly' 
      };
    } catch (error) {
      console.error('API server health check failed:', error);
      throw new Error('API server is not running or not accessible. Please start the API server using "python scripts/mongo_api_server.py --port 5001"');
    }
  },
  
  // Fetch a single trip by ID
  getTrip: async (id: string): Promise<Trip> => {
    try {
      if (!id || typeof id !== 'string') {
        throw new Error(`Invalid trip ID: ${id}. Expected a non-empty string.`);
      }
      
      // Clean the ID - remove any quotes or extra spaces
      const cleanId = id.trim().replace(/^["'](.*)["']$/, '$1');
      
      console.log(`Fetching trip ${cleanId} from API server...`);
      console.log('Original ID:', id);
      console.log('Cleaned ID:', cleanId);
      
      // Try to fetch from API server
      const response = await axios.get(`${API_BASE_URL}/trips/${cleanId}`);
      console.log('API response:', response.data);
      
      if (response.data) {
        return response.data;
      }
      
      throw new Error('Invalid response from API server');
    } catch (error) {
      console.error(`Error fetching trip ${id} from API server:`, error);
      
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        throw new Error(`Trip with ID ${id} not found. Please check the ID and try again.`);
      }
      
      throw new Error(`Failed to fetch trip ${id}. Please ensure the API server is running and connected to MongoDB.`);
    }
  },
  
  // Fetch trip calendar items by trip ID
  getTripCalendar: async (tripId: string): Promise<TripCalendarItem[]> => {
    try {
      if (!tripId || typeof tripId !== 'string') {
        console.error('Invalid trip ID type:', typeof tripId, tripId);
        throw new Error(`Invalid trip ID: ${String(tripId)}. Expected a non-empty string.`);
      }
      
      // Clean the ID - remove any quotes or extra spaces
      const cleanId = tripId.trim().replace(/^["'](.*)["']$/, '$1');
      
      console.log(`Fetching calendar for trip ${cleanId} from API server...`);
      console.log('Original ID:', tripId);
      console.log('Cleaned ID:', cleanId);
      
      // Try to fetch from API server - fix the URL by removing the extra /api prefix
      const response = await axios.get(`${API_BASE_URL}/calendar/${cleanId}`);
      console.log('API response:', response.data);
      
      if (response.data && Array.isArray(response.data)) {
        return response.data;
      }
      
      throw new Error('Invalid response from API server');
    } catch (error) {
      console.error(`Error fetching calendar for trip ${tripId} from API server:`, error);
      
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        throw new Error(`Calendar items for trip ${tripId} not found. Please check the trip ID and try again.`);
      }
      
      throw new Error(`Failed to fetch calendar items for trip ${tripId}. Please ensure the API server is running and MongoDB is accessible.`);
    }
  },

  // Delete a trip and its calendar items by trip ID
  deleteTrip: async (tripId: string): Promise<{ success: boolean; message: string }> => {
    try {
      console.log(`Deleting trip with ID: ${tripId}...`);
      
      // Delete trip from MongoDB
      const response = await axios.delete(`${API_BASE_URL}/trips/${tripId}`);
      console.log('API response for delete trip:', response.data);
      
      if (response.data && response.data.success) {
        return {
          success: true,
          message: response.data.message || 'Trip successfully deleted'
        };
      }
      
      throw new Error(response.data.error || 'Failed to delete trip');
    } catch (error) {
      console.error('Error deleting trip from MongoDB:', error);
      throw error instanceof Error 
        ? error 
        : new Error('An unknown error occurred while deleting the trip');
    }
  },
  
  // Fetch hotel recommendations for a trip
  getHotelRecommendations: async (tripId: string): Promise<TripCalendarItem[]> => {
    try {
      console.log(`Fetching hotel recommendations for trip with ID: ${tripId}...`);
      
      // Get a single hotel recommendation from MongoDB API
      const response = await axios.get(`${API_BASE_URL}/hotels/${tripId}?limit=1`);
      console.log('API response for hotel recommendations:', response.data);
      
      if (response.data && Array.isArray(response.data)) {
        return response.data;
      }
      
      throw new Error('Invalid response from API server');
    } catch (error) {
      console.error('Error fetching hotel recommendations:', error);
      throw error instanceof Error 
        ? error 
        : new Error('Failed to fetch hotel recommendations');
    }
  },
  
  // Add a hotel to the trip calendar
  addHotelToCalendar: async (tripId: string, hotelData: TripCalendarItem): Promise<TripCalendarItem> => {
    try {
      console.log(`Adding hotel to trip calendar for trip ID: ${tripId}...`);
      console.log('Hotel data:', hotelData);
      
      // Direct MongoDB operation to add the calendar item
      // We need to add the item directly to the trips collection as a calendar item
      // Remove any unnecessary fields before saving
      const { original_data, ...cleanedHotelData } = hotelData as any;
      
      // POST to the trips API endpoint with calendar item data
      const response = await axios.post(`${API_BASE_URL}/trips/${tripId}/calendar`, cleanedHotelData);
      console.log('API response for adding hotel to calendar:', response.data);
      
      if (response.data && response.data._id) {
        return response.data;
      }
      
      throw new Error('Failed to add hotel to trip calendar');
    } catch (error) {
      console.error('Error adding hotel to trip calendar:', error);
      throw error instanceof Error 
        ? error 
        : new Error('An unknown error occurred while adding the hotel to the trip calendar');
    }
  },
  
  // Search for and save a hotel recommendation in one call
  searchAndSaveHotelRecommendation: async (tripId: string): Promise<TripCalendarItem> => {
    try {
      console.log(`Searching for and saving a hotel recommendation for trip ID: ${tripId}...`);
      
      // Call the combined endpoint
      const response = await axios.post(`${API_BASE_URL}/hotels/${tripId}/save`);
      console.log('API response for hotel search and save:', response.data);
      
      if (response.data && response.data._id) {
        return response.data;
      }
      
      throw new Error('Failed to get and save hotel recommendation');
    } catch (error) {
      console.error('Error getting and saving hotel recommendation:', error);
      
      // Check if it's our special "no hotels" error
      if (error instanceof Error && error.message === 'NO_RESULTS_FOUND') {
        throw new Error('NO_RESULTS_FOUND');
      }
      
      throw error instanceof Error 
        ? error 
        : new Error('Failed to get and save hotel recommendation');
    }
  }
};
