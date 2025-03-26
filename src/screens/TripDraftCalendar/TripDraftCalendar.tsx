import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Button } from "../../components/ui/button";
import { CalendarIcon, MapPinIcon, UserIcon, ArrowRightIcon, PlusIcon, Trash2Icon } from 'lucide-react';
import { api } from "../../services/api";
import { useTripContext } from '../../contexts/TripContext';
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { cn } from "../../lib/utils";

// Simple fallback error component
const ErrorFallback = ({ error, resetError }: { error: Error | null, resetError?: () => void }) => (
  <div className="max-w-md mx-auto h-screen bg-white flex flex-col">
    <div className="p-4 border-b">
      <h1 className="text-xl font-medium text-center">Viammo</h1>
    </div>
    <div className="p-6 flex-1 flex flex-col items-center justify-center">
      <div className="p-4 bg-red-50 rounded-lg text-red-700 w-full max-w-sm">
        <h2 className="text-lg font-bold mb-2">Something went wrong</h2>
        <p className="mb-4">{error ? error.message : 'An unknown error occurred'}</p>
        <div className="space-y-2">
          {resetError && (
            <Button 
              className="w-full mb-2" 
              onClick={resetError}
            >
              Try Again
            </Button>
          )}
          <Button 
            className="w-full" 
            onClick={() => window.location.href = '/trips'}
          >
            Return to Trips
          </Button>
        </div>
      </div>
    </div>
  </div>
);

// Custom dialog without X button for mobile
const MobileDialog = DialogPrimitive.Root;

const MobileDialogPortal = ({
  ...props
}: DialogPrimitive.DialogPortalProps) => (
  <DialogPrimitive.Portal {...props} />
);

const MobileDialogOverlay = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      "fixed inset-0 z-50 bg-black/80 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
      className
    )}
    {...props}
  />
));

const MobileDialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <MobileDialogPortal>
    <MobileDialogOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        "fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border border-slate-200 bg-white shadow-lg duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%] sm:rounded-lg md:w-full",
        className
      )}
      {...props}
    >
      {children}
      {/* No close button here */}
    </DialogPrimitive.Content>
  </MobileDialogPortal>
));

const TripDraftCalendar: React.FC = () => {
  console.log("TripDraftCalendar component render started");

  const navigate = useNavigate();
  const { id: rawPathId } = useParams<{ id?: string }>();
  
  // Get trip context for state persistence
  const { 
    currentTripId, setCurrentTripId,
    currentTrip, setCurrentTrip,
    calendarItems, setCalendarItems
  } = useTripContext();
  
  // Local state for UI control
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [fatalError, setFatalError] = useState<Error | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // Process the trip ID from URL parameter correctly
  const pathId = rawPathId ? decodeURIComponent(rawPathId) : null;
  console.log("Raw path ID:", rawPathId);
  console.log("Decoded path ID:", pathId);
  
  // Create a safe version of the fetchData function
  const fetchData = useCallback(async () => {
    try {
      console.log("=== FETCH DATA STARTED ===");
      setLoading(true);
      setError(null);
      
      // First check if we already have the trip ID in context
      let tripId = currentTripId;
      console.log("Current trip ID from context:", tripId);
      
      // If not in context, try to get from URL path parameter
      if (!tripId && pathId) {
        console.log("Using trip ID from URL path:", pathId);
        tripId = pathId;
        
        // Save to context for future use
        setCurrentTripId(tripId);
      }
      
      // If still no trip ID, show error
      if (!tripId) {
        console.error("No trip ID provided in URL or context");
        throw new Error('No trip ID provided. Please select a trip from the trips list.');
      }
      
      console.log("Final trip ID to use:", tripId);
      
      // Check if we already have the trip data cached in context
      if (!currentTrip) {
        console.log("Fetching trip data from API for ID:", tripId);
        try {
          // Fetch trip data
          const tripData = await api.getTrip(tripId);
          console.log("API Response - Trip Data:", tripData);
          
          if (!tripData) {
            throw new Error('Trip data returned was empty');
          }
          
          setCurrentTrip(tripData);
        } catch (tripError) {
          console.error("Error fetching trip data:", tripError);
          throw new Error(`Failed to load trip details: ${tripError instanceof Error ? tripError.message : 'Unknown error'}`);
        }
      } else {
        console.log("Using cached trip data from context:", currentTrip);
      }
      
      // Always fetch fresh calendar items to ensure up-to-date data
      console.log("Fetching calendar items for trip ID:", tripId);
      try {
        const calendarData = await api.getTripCalendar(tripId);
        console.log("API Response - Calendar Data:", calendarData);
        
        if (Array.isArray(calendarData)) {
          setCalendarItems(calendarData);
        } else {
          console.warn("Calendar data is not an array, setting empty array");
          setCalendarItems([]);
        }
      } catch (calendarError) {
        console.error("Error fetching calendar data:", calendarError);
        setCalendarItems([]);
        setError(`Could not load calendar items: ${calendarError instanceof Error ? calendarError.message : 'Unknown error'}`);
      }
      
      console.log("=== FETCH DATA COMPLETED SUCCESSFULLY ===");
    } catch (err) {
      console.error('=== FETCH DATA FAILED ===');
      console.error('Error in fetchData:', err);
      setError(err instanceof Error ? err.message : 'Unknown error occurred');
    } finally {
      setLoading(false);
    }
  }, [pathId, currentTripId, currentTrip, setCurrentTripId, setCurrentTrip, setCalendarItems]);

  // Use effect hook to fetch data
  useEffect(() => {
    console.log("useEffect triggered for fetchData");
    fetchData().catch(err => {
      console.error("Unhandled error in fetchData effect:", err);
      setError(`Unhandled error: ${err instanceof Error ? err.message : 'Unknown error'}`);
      setLoading(false);
    });
  }, [fetchData]);

  // Format date function
  const formatDate = (dateString: string) => {
    try {
      if (!dateString) return '';
      const date = new Date(dateString);
      return `${date.getMonth() + 1}/${date.getDate()}/${String(date.getFullYear()).substring(2)}`;
    } catch (err) {
      return 'Invalid Date';
    }
  };
  
  // Format budget to price indicator
  const formatBudget = (budget: string | number | undefined): string => {
    if (budget === undefined || budget === null) return '';
    
    // Convert to string if it's a number
    const budgetStr = typeof budget === 'number' ? String(budget) : budget;
    
    // If the budget is already formatted with $ signs, return it as is
    if (budgetStr.includes('$')) {
      return budgetStr;
    }
    
    // Map budget to price indicators
    switch (budgetStr.toLowerCase()) {
      case '1':
      case 'low':
      case 'budget':
        return '$';
      case '2':
      case 'medium':
      case 'moderate':
        return '$$';
      case '3':
      case 'high':
      case 'expensive':
        return '$$$';
      case '4':
      case 'luxury':
      case 'very expensive':
        return '$$$$';
      default:
        // If budget is a number like 1-4, convert it
        const budgetNum = parseInt(budgetStr);
        if (!isNaN(budgetNum) && budgetNum >= 1 && budgetNum <= 4) {
          return '$'.repeat(budgetNum);
        }
        return '';
    }
  };
  
  // Simple navigation handlers
  const handleBackToTrips = () => navigate('/trips');
  const handleItemClick = (id: any) => {
    try {
      let itemId;
      if (typeof id === 'object' && id !== null && (id as any).$oid) {
        itemId = (id as any).$oid;
      } else {
        itemId = String(id);
      }
      console.log("Navigating to item with ID:", itemId);
      navigate(`/trip-element-detail/${encodeURIComponent(itemId)}`);
    } catch (err) {
      console.error("Error in handleItemClick:", err);
      setError(`Failed to navigate: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };
  
  const handleAddSpots = () => {
    try {
      alert('Add Spots & Requests functionality not implemented yet');
    } catch (err) {
      console.error("Error in handleAddSpots:", err);
    }
  };

  const handleDeleteTrip = () => {
    try {
      setDeleteDialogOpen(true);
    } catch (err) {
      console.error("Error in handleDeleteTrip:", err);
    }
  };

  const confirmDelete = async () => {
    if (!currentTripId) return;
    
    try {
      setIsDeleting(true);
      const result = await api.deleteTrip(currentTripId);
      if (result.success) {
        console.log(result.message);
        // Navigate back to trips list after deletion
        navigate('/trips');
      } else {
        throw new Error(result.message);
      }
    } catch (error) {
      console.error("Error deleting trip:", error);
      setError(`Failed to delete trip: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsDeleting(false);
      setDeleteDialogOpen(false);
    }
  };

  const cancelDelete = () => {
    setDeleteDialogOpen(false);
  };

  const resetError = () => {
    setError(null);
    setFatalError(null);
    fetchData().catch(console.error);
  };

  // If there's a fatal error, show the error component
  if (fatalError) {
    return <ErrorFallback error={fatalError} resetError={resetError} />;
  }

  try {
    // Render the component
    return (
      <div className="max-w-md mx-auto h-screen bg-white flex flex-col">
        {/* Header with back button and title */}
        <div className="flex items-center p-4 border-b">
          <button 
            onClick={handleBackToTrips}
            className="p-2 rounded-full hover:bg-gray-100"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M19 12H5M5 12L12 19M5 12L12 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
          <h1 className="text-xl font-medium text-center flex-1">Viammo</h1>
          <div className="w-8"></div>
        </div>

        {/* Trip Title */}
        <div className="px-4 py-3">
          <h2 className="text-2xl font-bold text-gray-900">
            {currentTrip?.name || (loading ? 'Loading...' : 'Trip Details')}
          </h2>
          {currentTripId && !loading && !currentTrip && (
            <p className="text-red-500 text-sm">Unable to load trip details</p>
          )}
        </div>

        {/* Separator Line */}
        <div className="w-full h-px bg-gray-200"></div>

        {/* Trip Info Bar */}
        <div className="flex px-4 py-3 gap-4 text-sm items-center flex-wrap">
          {currentTrip?.startDate && currentTrip?.endDate && (
            <div className="flex items-center gap-1.5">
              <CalendarIcon className="h-4 w-4 text-emerald-500" />
              <span className="text-emerald-500">{formatDate(currentTrip.startDate)}-{formatDate(currentTrip.endDate)}</span>
            </div>
          )}
          
          {currentTrip?.destination && (
            <div className="flex items-center gap-1.5">
              <MapPinIcon className="h-4 w-4 text-emerald-500" />
              <span className="text-emerald-500">{currentTrip.destination}</span>
            </div>
          )}
          
          {currentTrip?.numberOfGuests && (
            <div className="flex items-center gap-1.5">
              <UserIcon className="h-4 w-4 text-emerald-500" />
              <span className="text-emerald-500">{currentTrip.numberOfGuests} {currentTrip.numberOfGuests === 1 ? "guest" : "guests"}</span>
            </div>
          )}
        </div>

        {/* Trip Activities List */}
        <div className="flex-1 px-4 pb-1 overflow-y-auto">
          {loading ? (
            <div className="text-center py-8 text-gray-500">Loading calendar items...</div>
          ) : error ? (
            <div className="p-4 bg-red-50 text-red-500 text-sm rounded-lg">
              <p className="font-bold mb-2">Error:</p>
              <p>{error}</p>
              <button 
                onClick={resetError}
                className="mt-3 text-sm bg-white text-red-500 border border-red-300 px-3 py-1 rounded"
              >
                Retry
              </button>
            </div>
          ) : calendarItems.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              No calendar items found for this trip.
            </div>
          ) : (
            <div className="space-y-3 pt-4">
              {calendarItems.map((item, index) => (
                <div 
                  key={index} 
                  className="bg-gray-50 rounded-xl p-4 flex justify-between items-center shadow-sm cursor-pointer hover:bg-gray-100 transition-colors"
                  onClick={() => handleItemClick(item._id)}
                >
                  <div>
                    <h3 className="font-medium text-gray-900">{item.name || 'Unnamed Activity'}</h3>
                    <p className="text-gray-500 text-sm mt-0.5">
                      {item.budget && (
                        <span className="font-medium">{formatBudget(item.budget)}</span>
                      )}
                      {item.budget && item.notes && (
                        <span> - </span>
                      )}
                      {item.notes && (
                        <span>{item.notes}</span>
                      )}
                    </p>
                  </div>
                  <ArrowRightIcon className="h-5 w-5 text-gray-400" />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Add Spots Button */}
        <div className="px-4 py-3">
          <button
            className="w-full py-3 bg-emerald-50 text-emerald-500 font-medium rounded-lg flex items-center justify-center hover:bg-emerald-100 transition-colors"
            onClick={handleAddSpots}
            disabled={loading}
          >
            <PlusIcon className="h-5 w-5 mr-2" />
            Add Spots & Requests
          </button>
        </div>

        {/* Delete Trip Button */}
        <div className="px-4 pb-5">
          <button
            className="w-full py-3 bg-red-50 text-red-500 font-medium rounded-lg flex items-center justify-center hover:bg-red-100 transition-colors"
            onClick={handleDeleteTrip}
            disabled={loading}
          >
            <Trash2Icon className="h-5 w-5 mr-2" />
            Delete Trip
          </button>
        </div>
        
        {/* Delete Confirmation Dialog */}
        <MobileDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
          <MobileDialogContent className="sm:max-w-md max-w-[90%] rounded-xl p-6 border-0">
            <h2 className="text-xl font-bold text-center mb-4">Delete Trip</h2>
            <p className="text-base text-center mb-6">
              Are you sure you want to delete this trip and all its activities? This action cannot be undone.
            </p>
            
            <div className="flex flex-col space-y-3">
              <button
                className="w-full py-4 bg-red-500 text-white font-medium rounded-lg hover:bg-red-600 transition-colors text-lg"
                onClick={confirmDelete}
                disabled={isDeleting}
              >
                {isDeleting ? 'Deleting...' : 'Delete Trip'}
              </button>
              <button
                className="w-full py-4 bg-gray-100 text-gray-800 font-medium rounded-lg hover:bg-gray-200 transition-colors text-lg"
                onClick={cancelDelete}
                disabled={isDeleting}
              >
                Cancel
              </button>
            </div>
          </MobileDialogContent>
        </MobileDialog>
        
        {/* Debug Information in Development */}
        {process.env.NODE_ENV === 'development' && (
          <div className="p-3 text-xs text-gray-500 border-t">
            <details>
              <summary className="cursor-pointer">Debug Info</summary>
              <div className="mt-2 p-2 bg-gray-100 rounded">
                <p>Trip ID (Path): {pathId || 'null'}</p>
                <p>Trip ID (Context): {currentTripId || 'null'}</p>
                <p>Trip Loaded: {currentTrip ? 'Yes' : 'No'}</p>
                <p>Calendar Items: {calendarItems.length}</p>
                <p>State: {loading ? 'Loading' : error ? 'Error' : 'Ready'}</p>
              </div>
            </details>
          </div>
        )}
      </div>
    );
  } catch (renderErr) {
    console.error("Critical render error:", renderErr);
    setFatalError(renderErr instanceof Error ? renderErr : new Error('Unknown render error'));
    return <ErrorFallback error={renderErr instanceof Error ? renderErr : new Error('Unknown render error')} resetError={resetError} />;
  }
};

export default TripDraftCalendar;
