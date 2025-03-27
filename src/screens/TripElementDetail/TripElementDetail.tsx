import { ArrowLeftIcon, PlusIcon } from "lucide-react";
import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
import { Separator } from "../../components/ui/separator";
import { useTripContext } from "../../contexts/TripContext";
import { TripCalendarItem } from "../../services/types";

export const TripElementDetail = (): JSX.Element => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const { currentTripId, currentTrip, calendarItems } = useTripContext();
  const [currentItem, setCurrentItem] = useState<TripCalendarItem | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  
  useEffect(() => {
    // Log what we have in context for debugging
    console.log("Detail view - Current trip ID in context:", currentTripId);
    console.log("Detail view - Current trip in context:", currentTrip);
    console.log("Detail view - Calendar items in context:", calendarItems);
    console.log("Looking for element with ID:", id);
    
    // If we somehow got here without a trip ID in context, go back to trips
    if (!currentTripId) {
      console.error("No trip ID in context, redirecting to trips");
      navigate('/trips');
      return;
    }

    if (!id) {
      setError("No element ID provided");
      setLoading(false);
      return;
    }

    try {
      // Find the trip element by ID in our calendarItems from context
      const element = calendarItems.find(item => {
        const itemId = typeof item._id === 'string' ? item._id : (item._id as any).$oid;
        const paramId = id.includes('/') ? id.split('/').pop() : id;
        
        console.log("Comparing IDs - Item ID:", itemId, "Param ID:", paramId);
        
        return itemId === paramId;
      });

      if (element) {
        console.log("Found element:", element);
        console.log("Element main_media:", element.main_media);
        console.log("Element main_media type:", typeof element.main_media);
        setCurrentItem(element);
      } else {
        console.error("Element not found with ID:", id);
        setError("Element not found");
      }
    } catch (err) {
      console.error("Error finding element:", err);
      setError("Error loading element details");
    } finally {
      setLoading(false);
    }
  }, [currentTripId, currentTrip, calendarItems, id, navigate]);

  // Format date for display
  const formatDate = (dateString: string | undefined): string => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('en-US', { month: 'numeric', day: 'numeric', year: '2-digit' }).format(date);
  };

  // Format price for display
  const formatPrice = (price: number | undefined): string => {
    if (!price) return '';
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(price);
  };

  // Generate trip details badges
  const getTripDetails = (): { label: string; width: string }[] => {
    const details = [];
    
    // Date range
    if (currentItem?.date) {
      const endDateStr = currentItem.endDate || currentItem.date;
      const dateRange = formatDate(currentItem.date) + (currentItem.date !== endDateStr ? ` - ${formatDate(endDateStr)}` : '');
      details.push({ label: dateRange, width: "w-[161px]" });
    }
    
    // Price
    if (currentItem?.cost) {
      const price = typeof currentItem.cost === 'number' 
        ? formatPrice(currentItem.cost)
        : `${formatPrice(currentItem.cost.min)}-${formatPrice(currentItem.cost.max)}`;
      details.push({ label: price, width: "w-[87px]" });
    }
    
    // Guests
    if (currentTrip?.numberOfGuests) {
      details.push({ 
        label: `${currentTrip.numberOfGuests} ${currentTrip.numberOfGuests === 1 ? 'guest' : 'guests'}`, 
        width: "w-[101px]" 
      });
    }
    
    return details;
  };

  const handleBack = () => {
    // Navigate back to trip calendar, including the tripId in the URL and setting a refresh state
    if (currentTripId) {
      console.log("Navigating back to calendar with tripId:", currentTripId);
      navigate(`/trip-draft-calendar/${encodeURIComponent(currentTripId)}`, {
        state: { forceRefresh: true, timestamp: Date.now() }
      });
    } else {
      // Fallback if somehow we don't have a trip ID
      navigate('/trips');
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-screen">
        <p>Loading...</p>
      </div>
    );
  }

  if (error || !currentItem) {
    return (
      <div className="flex flex-col justify-center items-center h-screen p-4">
        <p className="text-red-500 mb-4">{error || "No item found"}</p>
        <Button onClick={handleBack}>Back to Calendar</Button>
      </div>
    );
  }

  return (
    <div className="bg-white flex flex-row justify-center w-full">
      <div className="bg-others-white relative w-[430px] h-[932px] overflow-hidden">
        {/* Status Bar */}
        <div className="absolute w-full h-11 top-0 left-0">
          <div className="absolute h-[26px] top-2 left-[23px] font-body-large-semibold text-others-black text-[length:var(--body-large-semibold-font-size)] tracking-[var(--body-large-semibold-letter-spacing)] leading-[var(--body-large-semibold-line-height)] whitespace-nowrap">
            9:41
          </div>
          <div className="absolute w-[18px] h-2.5 top-[18px] left-[336px] bg-[url(https://c.animaapp.com/m8dlap7ryGvklH/img/exclude.svg)] bg-[100%_100%]" />
          <div className="w-[15px] h-[11px] top-[17px] left-[359px] bg-[url(https://c.animaapp.com/m8dlap7ryGvklH/img/union.svg)] absolute bg-[100%_100%]" />
          <div className="w-[27px] h-[13px] top-4 left-[380px] bg-[url(https://c.animaapp.com/m8dlap7ryGvklH/img/group.png)] absolute bg-[100%_100%]" />
        </div>

        {/* Header with back button and title */}
        <div className="absolute w-[382px] h-12 top-11 left-9">
          <div className="flex w-full h-12 items-center gap-4 px-0 py-3">
            <Button variant="ghost" size="icon" className="w-7 h-7 p-0" onClick={handleBack}>
              <ArrowLeftIcon className="w-7 h-7" />
            </Button>
            <div className="flex-1 font-h4-bold text-greyscale-900 text-[length:var(--h4-bold-font-size)] text-center tracking-[var(--h4-bold-letter-spacing)] leading-[var(--h4-bold-line-height)]">
              Viammo
            </div>
            <div className="w-7" />
          </div>
        </div>

        {/* Hotel Name */}
        <div className="absolute w-[382px] h-[38px] top-[100px] left-[26px]">
          <div className="flex w-[382px] items-center gap-4">
            <div className="flex-1 font-h4-bold text-greyscale-900 text-[length:var(--h4-bold-font-size)] tracking-[var(--h4-bold-letter-spacing)] leading-[var(--h4-bold-line-height)]">
              {currentItem.name}
            </div>
          </div>
        </div>

        <Separator className="absolute w-[386px] h-px top-[146px] left-[23px]" />

        {/* Trip Details Badges */}
        <div className="absolute top-[164px] left-[23px] flex gap-2">
          {getTripDetails().map((detail, index) => (
            <Badge
              key={index}
              variant="outline"
              className={`${detail.width} h-[42px] rounded-[100px] border-2 border-[#17ce92] bg-transparent px-5 py-2 flex items-center justify-center`}
            >
              <span className="font-body-large-semibold text-primary-900 text-[length:var(--body-large-semibold-font-size)] tracking-[var(--body-large-semibold-letter-spacing)] leading-[var(--body-large-semibold-line-height)]">
                {detail.label}
              </span>
            </Badge>
          ))}
        </div>

        {/* Item Image */}
        <Card className="absolute w-[382px] h-[296px] top-[218px] left-[22px] border-none rounded-lg overflow-hidden">
          <CardContent className="p-0 h-full relative">
            <img
              className="w-full h-full object-cover"
              alt={currentItem.name}
              src={typeof currentItem.main_media === 'string' 
                ? currentItem.main_media 
                : (currentItem.main_media?.url || 'https://via.placeholder.com/382x296?text=No+Image+Available')}
              onError={(e) => {
                console.error("Image failed to load:", e);
                (e.target as HTMLImageElement).src = 'https://via.placeholder.com/382x296?text=No+Image+Available';
              }}
            />
            {currentItem.notes && (
              <div className="absolute bottom-4 right-4 font-body-xsmall-regular text-white text-[length:var(--body-xsmall-regular-font-size)] tracking-[var(--body-xsmall-regular-letter-spacing)] leading-[var(--body-xsmall-regular-line-height)]">
                {currentItem.notes}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Item Description */}
        <div className="absolute w-[382px] h-[130px] top-[525px] left-7">
          <div className="flex flex-col w-[382px] items-start gap-4">
            <p className="font-body-large-bold text-greyscale-900 text-[length:var(--body-large-bold-font-size)] tracking-[var(--body-large-bold-letter-spacing)] leading-[var(--body-large-bold-line-height)]">
              {currentItem.description || "No description available."}
            </p>
          </div>
        </div>

        {/* Replace Options Button */}
        <Button
          variant="outline"
          className="absolute w-[382px] h-[65px] top-[714px] left-[21px] bg-primary-50 text-primary-900 rounded-[100px] border-none flex items-center justify-center gap-4"
        >
          <PlusIcon className="w-5 h-5" />
          <span className="font-body-xlarge-bold text-primary-900 text-[length:var(--body-xlarge-bold-font-size)] tracking-[var(--body-xlarge-bold-letter-spacing)] leading-[var(--body-xlarge-bold-line-height)]">
            Replace with other options
          </span>
        </Button>

        {/* Add to Itinerary Button */}
        <div className="absolute w-[430px] h-[125px] top-[806px] left-px">
          <div className="flex flex-col w-[430px] items-start gap-6 pt-6 pb-9 px-6 bg-others-white border-t border-neutral-100">
            <Button className="w-full h-[56px] bg-primary-900 shadow-button-shadow-1 rounded-[100px] py-[18px]">
              <span className="font-body-xlarge-bold text-others-white text-[length:var(--body-xlarge-bold-font-size)] text-center tracking-[var(--body-xlarge-bold-letter-spacing)] leading-[var(--body-xlarge-bold-line-height)]">
                Add to itinerary
              </span>
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};
