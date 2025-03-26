// MongoDB ID format (supports both string and ObjectId format)
export interface MongoId {
  $oid?: string; // MongoDB ObjectId format from API responses
}

// MongoDB Trip Collection Interface
export interface Trip {
  _id: string | MongoId;
  name: string;
  startDate: string;
  endDate: string;
  destination: string;
  numberOfGuests: number;
  status?: string;
  totalBudget?: string | number;
  notes?: string;
  image?: string;
}

// MongoDB Trip Calendar Collection Interface
export interface TripCalendarItem {
  _id: string | MongoId;
  trip_id: string | MongoId;
  type: 'accommodation' | 'dining' | 'attraction' | 'shopping' | 'transportation' | 'other' | 'restaurants';
  name: string;
  date: string;
  endDate?: string;
  // Support for both date-time fields from MongoDB response
  start_date?: string;
  end_date?: string;
  start_time?: string;
  end_time?: string;
  // Support for cost fields in different formats
  min_cost?: number;
  max_cost?: number;
  timeSlot?: 'morning' | 'afternoon' | 'evening' | 'night' | 'all-day' | 'dinner';
  duration?: number;
  duration_minutes?: number;
  location?: {
    name: string;
    address?: string;
    coordinates?: {
      lat: number;
      lng: number;
    }
  } | string; // Allow location to be a string or an object
  cost?: number | {
    min: number;
    max: number;
  };
  // Budget field to represent price level (1-4 or strings like 'low', 'medium', 'high', 'luxury')
  budget?: string | number;
  currency?: string;
  rating?: string;
  ratingSource?: string;
  notes?: string;
  status?: 'confirmed' | 'planned' | 'cancelled' | 'draft';
  createdAt?: string;
  updatedAt?: string;
  description?: string; // Detailed description of the trip item
  main_media?: {
    url: string;
    alt?: string;
    caption?: string;
  };
}
