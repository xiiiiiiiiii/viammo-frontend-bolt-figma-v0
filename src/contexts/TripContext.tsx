import React, { createContext, useContext, useState, ReactNode } from 'react';
import { Trip, TripCalendarItem } from '../services/types';

interface TripContextType {
  currentTripId: string | null;
  setCurrentTripId: (id: string | null) => void;
  currentTrip: Trip | null;
  setCurrentTrip: (trip: Trip | null) => void;
  calendarItems: TripCalendarItem[];
  setCalendarItems: (items: TripCalendarItem[]) => void;
  clearTripData: () => void;
}

// Create the context with default values
const TripContext = createContext<TripContextType>({
  currentTripId: null,
  setCurrentTripId: () => {},
  currentTrip: null,
  setCurrentTrip: () => {},
  calendarItems: [],
  setCalendarItems: () => {},
  clearTripData: () => {},
});

// Export the custom hook for using this context
export const useTripContext = () => useContext(TripContext);

interface TripProviderProps {
  children: ReactNode;
}

export const TripProvider: React.FC<TripProviderProps> = ({ children }) => {
  const [currentTripId, setCurrentTripId] = useState<string | null>(null);
  const [currentTrip, setCurrentTrip] = useState<Trip | null>(null);
  const [calendarItems, setCalendarItems] = useState<TripCalendarItem[]>([]);

  // Function to clear all trip data (useful for logout or reset)
  const clearTripData = () => {
    setCurrentTripId(null);
    setCurrentTrip(null);
    setCalendarItems([]);
  };

  return (
    <TripContext.Provider
      value={{
        currentTripId,
        setCurrentTripId,
        currentTrip,
        setCurrentTrip,
        calendarItems,
        setCalendarItems,
        clearTripData,
      }}
    >
      {children}
    </TripContext.Provider>
  );
};

export default TripContext;
