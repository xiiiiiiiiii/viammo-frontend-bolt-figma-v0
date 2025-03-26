import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Calendar, MapPin, Users } from "lucide-react";
import { Button } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
import { Separator } from "../../components/ui/separator";
import { api } from "../../services/api";
import { Trip } from "../../services/types";
import { useTripContext } from "../../contexts/TripContext";

export const Trips = (): JSX.Element => {
  const navigate = useNavigate();
  const [trips, setTrips] = useState<Trip[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [apiStatus, setApiStatus] = useState<{ status: string; message: string } | null>(null);

  // Get trip context for state persistence
  const { setCurrentTripId, setCurrentTrip, setCalendarItems } = useTripContext();

  // Helper function to format trip date for display
  const formatDate = (dateString: string): string => {
    if (!dateString) return "TBD";
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  // Format status for display
  const formatStatus = (status: string | undefined): string => {
    return status ? status.charAt(0).toUpperCase() + status.slice(1) : "Draft";
  };

  // Fetch trips from API
  useEffect(() => {
    const fetchTrips = async () => {
      try {
        setLoading(true);
        setError(null);
        console.log("Attempting to fetch trips...");

        // Check API health first
        try {
          const healthStatus = await api.checkApiHealth();
          setApiStatus(healthStatus);
          if (healthStatus.status !== "ok") {
            console.error("API is not healthy:", healthStatus);
            setError(`API server is not available: ${healthStatus.message}`);
            setLoading(false);
            setTrips([]);
            return; // Exit early if API is not available
          }
        } catch (err) {
          console.error("Error checking API health:", err);
          setError("Cannot connect to the API server. Please ensure it's running.");
          setLoading(false);
          setTrips([]);
          return; // Exit early if API is not available
        }

        // If API is healthy, fetch trips
        const tripData = await api.getTrips();
        setTrips(tripData);

        if (tripData.length === 0) {
          // If no trips found but API is running, show a specific message
          setError("No trips found in the database. The API server is running correctly, but the MongoDB collection may be empty.");
        } else {
          setError(null);
        }
      } catch (err) {
        console.error("Error fetching trips:", err);
        setError("An error occurred while fetching trips. Check the console for details.");
      } finally {
        setLoading(false);
      }
    };

    fetchTrips();
  }, []);

  // Handle trip card click - Navigate to trip details
  const handleTripClick = (trip: Trip) => {
    const tripId = getFormattedTripId(trip);
    console.log(`Navigating to trip: ${tripId}`);
    // Set the current trip in context before navigating
    setCurrentTripId(tripId);
    setCurrentTrip(trip);
    // Clear any calendar items when navigating
    setCalendarItems([]);
    // Navigate to the trip detail page
    navigate(`/trip-draft-calendar/${encodeURIComponent(tripId)}`);
  };

  // Helper function to get a consistent trip ID format
  const getFormattedTripId = (trip: Trip): string => {
    return typeof trip._id === 'string' ? trip._id : (trip._id as any).$oid || JSON.stringify(trip._id);
  };

  const handleCreateNewTrip = () => {
    navigate('/build-new-trip/new');
  };

  return (
    <div className="h-full bg-white">
      {/* Status Bar and Header */}
      <div className="w-full border-b pb-2">
        <div className="flex w-full h-12 items-center gap-4 px-9 py-3">
          <h1 className="relative flex-1 font-h4-bold text-greyscale-900 text-[length:var(--h4-bold-font-size)] text-center tracking-[var(--h4-bold-letter-spacing)] leading-[var(--h4-bold-line-height)]">
            Viammo
          </h1>
        </div>
      </div>

      <div className="mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Trips Subtitle */}
        <div className="flex max-w-md mx-auto items-center gap-4 mb-4 px-2">
          <h2 className="font-h4-bold text-greyscale-900 text-[length:var(--h4-bold-font-size)] tracking-[var(--h4-bold-letter-spacing)] leading-[var(--h4-bold-line-height)]">
            Trips
          </h2>
        </div>

        <div className="max-w-md mx-auto">
          <Separator className="mb-6" />
        </div>

        <div className="space-y-4 max-w-md mx-auto px-4">
          {loading ? (
            <div className="p-4 text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500 mx-auto"></div>
              <p className="mt-2 text-gray-500">Loading trips...</p>
            </div>
          ) : error ? (
            <div className="p-4 bg-red-50 text-red-800 rounded-md">
              <p className="font-medium">Error:</p>
              <p>{error}</p>
              <p className="mt-2 text-sm">
                {apiStatus && apiStatus.status !== "ok" ? (
                  <span>
                    API Status: {apiStatus.status} - {apiStatus.message}
                  </span>
                ) : (
                  <span>Check that the MongoDB API server is running.</span>
                )}
              </p>
            </div>
          ) : trips.length === 0 ? (
            <div className="p-4 text-center text-gray-500">
              No trips found. Create a new trip to get started.
            </div>
          ) : (
            trips.map((trip) => {
              const tripId = getFormattedTripId(trip);
              return (
                <Card
                  key={tripId}
                  className="w-full hover:bg-gray-100 cursor-pointer transition-colors bg-gray-50 rounded-lg overflow-hidden shadow-sm relative"
                  onClick={() => handleTripClick(trip)}
                >
                  <CardContent className="p-4">
                    <div className="flex justify-between items-start">
                      <div className="flex-1 pr-20">
                        <h3 className="text-lg font-semibold font-h4-bold text-greyscale-900 text-[length:var(--body-large-bold-font-size)] tracking-[var(--body-large-bold-letter-spacing)] leading-[var(--body-large-bold-line-height)]">{trip.name}</h3>

                        {/* Trip summary info with icons on a single line */}
                        <div className="flex items-center flex-nowrap whitespace-nowrap text-[#00C29A] mt-2">
                          <Calendar className="h-4 w-4 mr-1" />
                          <span className="text-sm mr-3">{formatDate(trip.startDate)}-{formatDate(trip.endDate)}</span>

                          <MapPin className="h-4 w-4 mr-1" />
                          <span className="text-sm mr-3">{trip.destination}</span>

                          <Users className="h-4 w-4 mr-1" />
                          <span className="text-sm">{trip.numberOfGuests || 3} guests</span>
                        </div>
                      </div>

                      {/* Status badge in top right */}
                      <div className="absolute top-4 right-4">
                        <span
                          className={`inline-block text-base font-medium ${
                            trip.status === "confirmed"
                              ? "text-green-600"
                              : trip.status === "draft"
                              ? "text-amber-500"
                              : "text-blue-600"
                          }`}
                        >
                          {formatStatus(trip.status)}
                        </span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })
          )}

          {/* Create New Trip Button */}
          <div className="py-8 px-6 max-w-md mx-auto">
            <Button
              className="w-full flex items-center justify-center gap-2 bg-[#10D394] hover:bg-[#00C29A] text-white font-medium py-4 rounded-full shadow-md text-lg transition-all"
              onClick={handleCreateNewTrip}
            >
              Create New Trip
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};
