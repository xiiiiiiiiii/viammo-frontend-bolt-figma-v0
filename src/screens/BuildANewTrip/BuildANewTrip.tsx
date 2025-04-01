import { PlusIcon, X as CloseIcon, Globe, ArrowLeft, Check } from "lucide-react";
import React, { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
import { Separator } from "../../components/ui/separator";
import { Switch } from "../../components/ui/switch";
import { 
  TextField, 
  createTheme,
  ThemeProvider,
  Popover,
  List,
  ListItem,
  ListItemText,
  Dialog,
  DialogTitle,
  DialogContent,
  IconButton
} from "@mui/material";
import axios from "axios";
import { useTripContext } from "../../contexts/TripContext";

// Create a theme that matches the app's styling
const theme = createTheme({
  palette: {
    primary: {
      main: '#334FB8',
    },
  },
  typography: {
    fontFamily: 'Arial, sans-serif',
  },
  components: {
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          borderRadius: '16px',
        },
      },
    },
    MuiSelect: {
      styleOverrides: {
        root: {
          borderRadius: '16px',
        },
      },
    },
    MuiRadio: {
      styleOverrides: {
        root: {
          color: '#e0e0e0',
          '&.Mui-checked': {
            color: '#334FB8',
          },
        },
      },
    },
    MuiListItem: {
      styleOverrides: {
        root: {
          '&:hover': {
            backgroundColor: '#f5f8ff',
          },
        },
      },
    },
  },
});

// City options for destination selection 
const cityOptionsDict: Record<string, {city: string, state: string, country: string}> = {
  "Aspen, CO, USA": { city: "Aspen", state: "CO", country: "USA" },
  "Paris, France": { city: "Paris", state: "", country: "France" },
  "London, UK": { city: "London", state: "", country: "UK" },
  "New York, NY, USA": { city: "New York", state: "NY", country: "USA" },
  "Tokyo, Japan": { city: "Tokyo", state: "", country: "Japan" },
  "Bali, Indonesia": { city: "Bali", state: "", country: "Indonesia" },
  "Barcelona, Spain": { city: "Barcelona", state: "", country: "Spain" },
  "Rome, Italy": { city: "Rome", state: "", country: "Italy" },
  "Sydney, Australia": { city: "Sydney", state: "", country: "Australia" },
  "Amsterdam, Netherlands": { city: "Amsterdam", state: "", country: "Netherlands" },
  "Bangkok, Thailand": { city: "Bangkok", state: "", country: "Thailand" },
  "Dubai, UAE": { city: "Dubai", state: "", country: "UAE" },
  "Singapore": { city: "Singapore", state: "", country: "Singapore" },
  "Hong Kong": { city: "Hong Kong", state: "", country: "China" },
  "Los Angeles, CA, USA": { city: "Los Angeles", state: "CA", country: "USA" },
  "San Francisco, CA, USA": { city: "San Francisco", state: "CA", country: "USA" },
  "Miami, FL, USA": { city: "Miami", state: "FL", country: "USA" },
  "Las Vegas, NV, USA": { city: "Las Vegas", state: "NV", country: "USA" },
  "Honolulu, HI, USA": { city: "Honolulu", state: "HI", country: "USA" },
  "Cancun, Mexico": { city: "Cancun", state: "", country: "Mexico" },
};

// Keep the original array for compatibility with existing code
const cityOptions = Object.keys(cityOptionsDict);

// Generate guest options from 1 to 20
const guestOptions = Array.from({ length: 20 }, (_, i) => i + 1);

// Budget options with descriptive labels
const budgetOptions = [
  { value: "$", label: "$ Budget-friendly" },
  { value: "$$", label: "$$ Moderate" },
  { value: "$$$", label: "$$$ Premium" },
  { value: "$$$$", label: "$$$$ Luxury" }
];

// Purpose options
const purposeOptions = [
  "Leisure",
  "Business",
  "Family vacation",
  "Adventure",
  "Honeymoon",
  "Cultural experience",
  "Food & wine tour",
  "Beach getaway",
  "City break",
  "Romantic retreat",
  "Solo travel",
  "Wellness retreat",
  "Educational trip",
  "Wedding",
  "Anniversary celebration",
  "Conference",
  "Sports event",
  "Music festival",
  "Photography trip",
  "Wildlife safari"
];

export const BuildANewTrip = (): JSX.Element => {
  const navigate = useNavigate();
  const { } = useParams<{ id: string }>();
  
  const { setCurrentTripId, setCurrentTrip } = useTripContext();
  
  // Function to handle back navigation
  const handleBack = () => {
    navigate(-1);
  };

  // State for destination selection
  const [destinationAnchorEl, setDestinationAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedDestination, setSelectedDestination] = useState<string | null>(null);
  const [selectedDestinationData, setSelectedDestinationData] = useState<{city: string, state: string, country: string} | null>(null);
  const [searchInput, setSearchInput] = useState<string>('');
  const [filteredCities, setFilteredCities] = useState<string[]>(cityOptions);

  // State for date display and picker
  const [calendarDate, setCalendarDate] = useState<Date>(new Date());
  const [showCalendar, setShowCalendar] = useState<'start' | 'end' | null>(null);

  // State for guest selection
  const [guestAnchorEl, setGuestAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedGuests, setSelectedGuests] = useState<number | null>(null);

  // State for budget selection 
  const [budgetAnchorEl, setBudgetAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedBudget, setSelectedBudget] = useState<string | null>(null);
  
  // State for purpose selection
  const [purposeAnchorEl, setPurposeAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedPurpose, setSelectedPurpose] = useState<string | null>(null);
  const [purposeInput, setPurposeInput] = useState<string>('');
  const [filteredPurposes, setFilteredPurposes] = useState<string[]>(purposeOptions);
  
  // State for details and requests
  const [detailsExpanded, setDetailsExpanded] = useState<boolean>(false);
  const [tripDetails, setTripDetails] = useState<string>('');
  
  // State for trip visibility
  const [isPublic, setIsPublic] = useState<boolean>(true);
  
  // State for trip name
  const [tripName, setTripName] = useState<string>('');
  
  // Error state
  const [error, setError] = useState<string | null>(null);
  
  // Loading state
  const [isCreating, setIsCreating] = useState<boolean>(false);

  // Function to get days in month
  const getDaysInMonth = (year: number, month: number) => {
    return new Date(year, month + 1, 0).getDate();
  };

  // Function to get day of week for the first day of month (0 = Sunday, 6 = Saturday)
  const getFirstDayOfMonth = (year: number, month: number) => {
    return new Date(year, month, 1).getDay();
  };

  // Generate calendar days
  const generateCalendarDays = () => {
    const year = calendarDate.getFullYear();
    const month = calendarDate.getMonth();
    
    const daysInMonth = getDaysInMonth(year, month);
    const firstDay = getFirstDayOfMonth(year, month);
    
    // Get some days from previous month
    const prevMonthDays = [];
    const prevMonth = month === 0 ? 11 : month - 1;
    const prevMonthYear = month === 0 ? year - 1 : year;
    const daysInPrevMonth = getDaysInMonth(prevMonthYear, prevMonth);
    
    for (let i = firstDay - 1; i >= 0; i--) {
      prevMonthDays.push({
        day: daysInPrevMonth - i,
        month: prevMonth,
        year: prevMonthYear,
        isCurrentMonth: false
      });
    }
    
    // Current month days
    const currentMonthDays = [];
    for (let i = 1; i <= daysInMonth; i++) {
      currentMonthDays.push({
        day: i,
        month,
        year,
        isCurrentMonth: true
      });
    }
    
    // Next month days to fill remaining slots (to make a 6-row calendar)
    const totalDaysShown = 42; // 6 rows of 7 days
    const nextMonthDays = [];
    const nextMonth = month === 11 ? 0 : month + 1;
    const nextMonthYear = month === 11 ? year + 1 : year;
    
    const remainingDays = totalDaysShown - prevMonthDays.length - currentMonthDays.length;
    for (let i = 1; i <= remainingDays; i++) {
      nextMonthDays.push({
        day: i,
        month: nextMonth,
        year: nextMonthYear,
        isCurrentMonth: false
      });
    }
    
    return [...prevMonthDays, ...currentMonthDays, ...nextMonthDays];
  };

  // Function to format month and year for display in calendar
  const getMonthYearString = () => {
    const options: Intl.DateTimeFormatOptions = { month: 'long', year: 'numeric' };
    return calendarDate.toLocaleDateString('en-US', options);
  };

  // Navigate to previous month
  const goToPreviousMonth = () => {
    setCalendarDate(prev => {
      const newDate = new Date(prev);
      newDate.setMonth(prev.getMonth() - 1);
      return newDate;
    });
  };

  // Navigate to next month
  const goToNextMonth = () => {
    setCalendarDate(prev => {
      const newDate = new Date(prev);
      newDate.setMonth(prev.getMonth() + 1);
      return newDate;
    });
  };

  // Handle day selection in calendar
  const handleDayClick = (year: number, month: number, day: number) => {
    const selectedDate = new Date(year, month, day);
    
    if (showCalendar === 'start') {
      setStartDate(selectedDate);
      
      // If start date is after end date, adjust end date
      if (endDate && selectedDate > endDate) {
        const newEndDate = new Date(selectedDate);
        newEndDate.setDate(selectedDate.getDate() + 7);
        setEndDate(newEndDate);
      }
      
      // Show end date picker next
      setShowCalendar('end');
    } else if (showCalendar === 'end') {
      // Ensure end date is not before start date
      if (startDate && selectedDate < startDate) {
        return; // Don't allow end date before start date
      }
      
      setEndDate(selectedDate);
      setShowCalendar(null); // Close calendar after end date is selected
    }
  };

  // Get today's date
  const today = new Date();
  const isToday = (day: number, month: number, year: number) => {
    return day === today.getDate() && 
           month === today.getMonth() && 
           year === today.getFullYear();
  };

  // Check if a date is the start date
  const isStartDate = (day: number, month: number, year: number) => {
    if (!startDate) return false;
    return day === startDate.getDate() && 
           month === startDate.getMonth() && 
           year === startDate.getFullYear();
  };
  
  // Check if a date is the end date
  const isEndDate = (day: number, month: number, year: number) => {
    if (!endDate) return false;
    return day === endDate.getDate() && 
           month === endDate.getMonth() && 
           year === endDate.getFullYear();
  };
  
  // Check if a date is selected (either start or end)
  const isSelected = (day: number, month: number, year: number) => {
    return isStartDate(day, month, year) || isEndDate(day, month, year);
  };
  
  // Check if a date is in range between start and end
  const isInRange = (day: number, month: number, year: number) => {
    if (!startDate || !endDate) return false;
    
    const date = new Date(year, month, day);
    return date > startDate && date < endDate;
  };

  // Function to go to today's date
  const goToToday = () => {
    setCalendarDate(new Date());
  };

  // Function to clear date selection
  const clearDateSelection = () => {
    if (showCalendar === 'start') {
      setStartDate(null);
    } else if (showCalendar === 'end') {
      setEndDate(null);
    }
    setShowCalendar(null);
  };

  // State for start and end dates
  const [startDate, setStartDate] = useState<Date | null>(null);
  const [endDate, setEndDate] = useState<Date | null>(null);

  // Format date for display (Month Day, Year)
  const formatDate = (date: Date | null): string => {
    if (!date) return '';
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  // State for trip options to enable mapping
  const tripOptions = [
    { id: 1, title: selectedDestination ? selectedDestination : "Add Destination" },
    { id: 5, title: startDate && endDate ? `${formatDate(startDate)} - ${formatDate(endDate)}` : "Add Dates" }, 
    { id: 2, title: selectedGuests ? `${selectedGuests} Guest${selectedGuests > 1 ? 's' : ''}` : "Add Guests" },
    { id: 3, title: selectedBudget || "Add Budget" },
    { id: 4, title: selectedPurpose || "Add Purpose" },
  ];

  const handleContinue = async () => {
    // Validate at least a destination is selected
    if (!selectedDestination) {
      setError("Please select a destination first");
      return;
    }
    
    try {
      setIsCreating(true);
      setError(null);
      
      // Get the dates as strings in ISO format
      const startDateStr = startDate ? startDate.toISOString() : new Date().toISOString();
      const endDateStr = endDate ? endDate.toISOString() : (() => {
        const oneWeekFromStart = new Date(startDateStr);
        oneWeekFromStart.setDate(oneWeekFromStart.getDate() + 7);
        return oneWeekFromStart.toISOString();
      })();
      
      // Format budget to save only dollar signs
      const formatBudgetToSymbols = (budgetString: string | null | undefined): string => {
        if (!budgetString) return "$"; // Default to $ if no budget is selected
        
        // Count the dollar signs in the string
        const dollarCount = (budgetString.match(/\$/g) || []).length;
        
        // Return just the dollar signs
        if (dollarCount > 0) {
          return "$".repeat(dollarCount);
        }
        
        // If no dollar signs found, parse the budget level from text
        if (budgetString.toLowerCase().includes("luxury") || budgetString.toLowerCase().includes("expensive")) {
          return "$$$$";
        } else if (budgetString.toLowerCase().includes("moderate") || budgetString.toLowerCase().includes("mid")) {
          return "$$";
        } else if (budgetString.toLowerCase().includes("premium") || budgetString.toLowerCase().includes("high")) {
          return "$$$";
        } else {
          return "$"; // Default to $ for budget/economy options
        }
      };
      
      const tripData = {
        name: tripName || `Trip to ${selectedDestination}`,
        startDate: startDateStr,
        endDate: endDateStr,
        destination: selectedDestinationData || { city: "", state: "", country: "" },
        numberOfGuests: selectedGuests || 1,
        status: 'draft',
        notes: tripDetails || "",
        totalBudget: formatBudgetToSymbols(selectedBudget),
        purpose: selectedPurpose || "Leisure",
        created_at: new Date().toISOString(),
        public: isPublic
      };

      console.log("Sending trip data:", tripData);
      const api_endpoint = 'http://localhost:5001/api/create_trip';
      console.log("API endpoint:", api_endpoint);
      
      // Send request to create a new trip
      const response = await axios.post(api_endpoint, tripData);
      
      console.log("API response:", response);
      
      if (response.data && response.data.trip_id) {
        // Save trip ID and data in context with the required _id field
        const tripWithId = {
          ...tripData,
          _id: response.data.trip_id
        };
        setCurrentTripId(response.data.trip_id);
        setCurrentTrip(tripWithId);
        
        // Navigate to the calendar view with the new trip ID
        navigate(`/trip-draft-calendar/${encodeURIComponent(String(response.data.trip_id))}`, {
          state: { fromBuildNewTrip: true }
        });
      } else {
        throw new Error("Failed to get trip ID from server: " + JSON.stringify(response.data));
      }
    } catch (error: unknown) { 
      console.error("Error creating trip:", error);
      
      // Type guard to check if error is an Axios error
      if (axios.isAxiosError(error)) {
        if (error.response) {
          // The request was made and the server responded with a status code
          // that falls out of the range of 2xx
          console.error("Response data:", error.response.data);
          console.error("Response status:", error.response.status);
          setError(`Failed to create trip: ${error.response.status} ${JSON.stringify(error.response.data)}`);
        } else if (error.request) {
          // The request was made but no response was received
          console.error("No response received:", error.request);
          setError("Failed to create trip: No response from server. Check if API server is running.");
        } else {
          // Something happened in setting up the request that triggered an Error
          setError(`Failed to create trip: ${error.message}`);
        }
      } else {
        // For non-Axios errors
        setError(`Failed to create trip: ${error instanceof Error ? error.message : 'Unknown error'}`);
      }
    } finally {
      setIsCreating(false);
    }
  };

  // Calculate positions for UI elements based on fixed positions similar to option cards
  const getCardPosition = (index: number) => {
    return 171 + (index * 78);
  };
  
  // Get the position for the "Add Details" button - right after the last option card
  const getDetailsPosition = () => {
    return getCardPosition(tripOptions.length);
  };
  
  // Get the position for the visibility toggle - after the details or after the last card + extra space
  const getVisibilityPosition = () => {
    return getCardPosition(tripOptions.length + 1);
  };
  
  // Get the position for the continue button - at the bottom
  const getContinueButtonPosition = () => {
    return getCardPosition(tripOptions.length + 2);
  };

  const handleDestinationCardClick = (event: React.MouseEvent<HTMLDivElement>) => {
    setDestinationAnchorEl(event.currentTarget);
    setFilteredCities(cityOptions);
  };

  const handleDestinationMenuClose = () => {
    setDestinationAnchorEl(null);
    setSearchInput('');
  };

  const handleDestinationSelect = (destination: string) => {
    setSelectedDestination(destination);
    setSelectedDestinationData(cityOptionsDict[destination]);
    handleDestinationMenuClose();
  };

  const handleSearchInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const input = event.target.value;
    setSearchInput(input);
    
    // Filter cities based on search input
    const filtered = cityOptions.filter(
      city => city.toLowerCase().includes(input.toLowerCase())
    );
    setFilteredCities(filtered);
  };

  const handleGuestCardClick = (event: React.MouseEvent<HTMLDivElement>) => {
    setGuestAnchorEl(event.currentTarget);
  };

  const handleGuestMenuClose = () => {
    setGuestAnchorEl(null);
  };

  const handleGuestSelect = (guests: number) => {
    setSelectedGuests(guests);
    handleGuestMenuClose();
  };

  const handleBudgetCardClick = (event: React.MouseEvent<HTMLDivElement>) => {
    setBudgetAnchorEl(event.currentTarget);
  };

  const handleBudgetMenuClose = () => {
    setBudgetAnchorEl(null);
  };

  const handleBudgetSelect = (budget: string) => {
    setSelectedBudget(budget);
    handleBudgetMenuClose();
  };
  
  const handlePurposeCardClick = (event: React.MouseEvent<HTMLDivElement>) => {
    setPurposeAnchorEl(event.currentTarget);
    setFilteredPurposes(purposeOptions);
  };

  const handlePurposeMenuClose = () => {
    setPurposeAnchorEl(null);
    setPurposeInput('');
  };

  const handlePurposeSelect = (purpose: string) => {
    setSelectedPurpose(purpose);
    handlePurposeMenuClose();
  };

  const handlePurposeInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const input = event.target.value;
    setPurposeInput(input);
    
    // Filter purposes based on search input
    const filtered = purposeOptions.filter(
      purpose => purpose.toLowerCase().includes(input.toLowerCase())
    );
    setFilteredPurposes(filtered);
  };

  // Function to determine if a card should be clickable based on its id
  const isCardClickable = (id: number) => {
    return id === 1 || id === 2 || id === 3 || id === 4 || id === 5; 
  };

  // Function to handle card click based on card id
  const handleCardClick = (id: number, event: React.MouseEvent<HTMLDivElement>) => {
    switch (id) {
      case 1:
        handleDestinationCardClick(event);
        break;
      case 2:
        handleGuestCardClick(event);
        break;
      case 3:
        handleBudgetCardClick(event);
        break;
      case 4:
        handlePurposeCardClick(event);
        break;
      case 5:
        if (startDate && endDate) {
          // If dates are already selected, ask which one to edit
          setShowCalendar('start');
        } else {
          // Otherwise default to selecting start date
          setShowCalendar('start');
        }
        break;
      default:
        break;
    }
  };

  return (
    <div className="relative bg-white flex flex-row justify-center w-full">
      <div className="bg-others-white overflow-hidden w-[430px] h-[932px] relative">
        {/* Status Bar */}
        <div className="absolute w-[430px] h-11 top-0 left-px">
          <div className="absolute h-[26px] top-2 left-[23px] font-body-large-semibold font-[number:var(--body-large-semibold-font-weight)] text-others-black text-[length:var(--body-large-semibold-font-size)] tracking-[var(--body-large-semibold-letter-spacing)] leading-[var(--body-large-semibold-line-height)] whitespace-nowrap [font-style:var(--body-large-semibold-font-style)]">
            9:41
          </div>
          <div className="absolute w-[18px] h-2.5 top-[18px] left-[336px] bg-[url(https://c.animaapp.com/m8dkp8hva61T8x/img/exclude.svg)] bg-[100%_100%]" />
          <div className="w-[15px] h-[11px] top-[17px] left-[359px] bg-[url(https://c.animaapp.com/m8dkp8hva61T8x/img/union.svg)] absolute bg-[100%_100%]" />
          <div className="w-[27px] h-[13px] top-4 left-[380px] bg-[url(https://c.animaapp.com/m8dkp8hva61T8x/img/group.png)] absolute bg-[100%_100%]" />
        </div>

        {/* Header with back button and title */}
        <div className="flex w-[382px] h-12 items-center gap-4 px-0 py-3 absolute top-11 left-9">
          <ArrowLeft
            className="w-6 h-6 cursor-pointer text-greyscale-900"
            onClick={handleBack}
          />
          <div className="relative flex-1 mt-[-8.00px] mb-[-6.00px] font-h4-bold font-[number:var(--h4-bold-font-weight)] text-greyscale-900 text-[length:var(--h4-bold-font-size)] text-center tracking-[var(--h4-bold-letter-spacing)] leading-[var(--h4-bold-line-height)] [font-style:var(--h4-bold-font-style)]">
            Viammo
          </div>
          <div className="w-7 justify-end gap-5 mt-[-2.00px] mb-[-2.00px] flex items-center relative" />
        </div>

        {/* Name your trip section */}
        <div className="flex w-[382px] items-center gap-4 absolute top-[100px] left-[25px]">
          <div className="relative flex-1 mt-[-1.00px] font-h4-bold font-[number:var(--h4-bold-font-weight)] text-greyscale-900 text-[length:var(--h4-bold-font-size)] tracking-[var(--h4-bold-letter-spacing)] leading-[var(--h4-bold-line-height)] [font-style:var(--h4-bold-font-style)]">
            <input
              type="text"
              value={tripName}
              onChange={(e) => setTripName(e.target.value)}
              placeholder="Name your trip"
              className="w-full bg-transparent outline-none border-none"
            />
          </div>
        </div>

        <Separator className="absolute w-[386px] h-px top-[146px] left-[23px]" />

        {/* Trip options cards */}
        {tripOptions.map((option, index) => (
          <Card
            key={option.id}
            className={`flex w-[382px] items-center gap-4 pl-5 pr-6 py-4 absolute bg-greyscale-50 rounded-2xl border border-solid border-[#eeeeee] ${isCardClickable(option.id) ? 'cursor-pointer hover:border-primary-900 hover:shadow-md' : ''}`}
            style={{
              top: `${getCardPosition(index)}px`,
              left: "23px",
            }}
            onClick={isCardClickable(option.id) ? (e) => handleCardClick(option.id, e) : undefined}
          >
            <CardContent className="p-0 flex items-center justify-between w-full">
              <div className="relative flex-1 mt-[-1.00px] font-h6-bold font-[number:var(--h6-bold-font-weight)] text-greyscale-900 text-[length:var(--h6-bold-font-size)] text-justify tracking-[var(--h6-bold-letter-spacing)] leading-[var(--h6-bold-line-height)] [font-style:var(--h6-bold-font-style)]">
                {option.title}
              </div>
              <div className="relative w-6 h-6 text-[#00C29A]">
                {(option.id === 1 && selectedDestination) || 
                 (option.id === 2 && selectedGuests !== null) || 
                 (option.id === 3 && selectedBudget) || 
                 (option.id === 4 && selectedPurpose) || 
                 (option.id === 5 && startDate && endDate) ? (
                  <Check size={24} />
                ) : (
                  <svg
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <circle
                      cx="12"
                      cy="12"
                      r="8"
                      stroke="currentColor"
                      strokeWidth="2"
                      fill="none"
                    />
                  </svg>
                )}
              </div>
            </CardContent>
          </Card>
        ))}

        {/* Add Details & Requests button */}
        {!detailsExpanded ? (
          <Button
            className="whitespace-nowrap text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 border border-input shadow-sm hover:bg-accent hover:text-accent-foreground h-9 w-[382px] absolute bg-primary-50 flex items-center justify-center gap-2.5 px-4 py-[18px] rounded-[100px] border-none"
            style={{
              top: `${getDetailsPosition()}px`,
              left: "23px",
            }}
            onClick={() => setDetailsExpanded(true)}
          >
            <PlusIcon className="w-5 h-5" />
            <span className="relative w-fit mt-[-1.00px] font-body-xlarge-bold font-[number:var(--body-xlarge-bold-font-weight)] text-primary-900 text-[length:var(--body-xlarge-bold-font-size)] text-center tracking-[var(--body-xlarge-bold-letter-spacing)] leading-[var(--body-xlarge-bold-line-height)] whitespace-nowrap [font-style:var(--body-xlarge-bold-font-style)]">
              Add Details & Requests
            </span>
          </Button>
        ) : (
          <div 
            className="absolute w-[382px]" 
            style={{
              top: `${getDetailsPosition()}px`,
              left: "23px",
            }}
          >
            <TextField
              fullWidth
              autoFocus
              value={tripDetails}
              onChange={(e) => setTripDetails(e.target.value)}
              placeholder="I'm allergic to boredom"
              variant="outlined"
              sx={{
                '& .MuiOutlinedInput-root': {
                  height: '56px',
                  borderRadius: '16px',
                  backgroundColor: '#F9F9F9',
                  fontFamily: 'var(--body-large-regular-font-family)',
                  fontSize: 'var(--body-large-regular-font-size)',
                  lineHeight: 'var(--body-large-regular-line-height)',
                  letterSpacing: 'var(--body-large-regular-letter-spacing)',
                },
                '& .MuiOutlinedInput-notchedOutline': {
                  borderColor: '#EEEEEE',
                },
                '& .MuiOutlinedInput-root:hover .MuiOutlinedInput-notchedOutline': {
                  borderColor: '#334FB8',
                },
                '& .MuiOutlinedInput-root.Mui-focused .MuiOutlinedInput-notchedOutline': {
                  borderColor: '#334FB8',
                },
                '& .MuiInputBase-input::placeholder': {
                  color: '#AAAAAA',
                  fontStyle: 'italic',
                  opacity: 0.8,
                },
              }}
              InputProps={{
                endAdornment: (
                  <CloseIcon 
                    className="cursor-pointer text-greyscale-500 hover:text-greyscale-900" 
                    onClick={() => {
                      setDetailsExpanded(false);
                      // Optionally clear text when closing
                      // setTripDetails('');
                    }}
                    size={20}
                  />
                ),
              }}
            />
          </div>
        )}

        {/* Trip visibility section */}
        <div 
          className="absolute w-[382px] flex flex-col items-end gap-2.5" 
          style={{
            top: `${getVisibilityPosition()}px`, 
            left: "23px"
          }}
        >
          <div 
            className={`flex items-center gap-2.5 p-2 rounded-[100px] border border-solid cursor-pointer ${isPublic ? 'bg-primary-50 border-primary-900' : 'bg-greyscale-50 border-[#EEEEEE]'}`}
            onClick={() => setIsPublic(!isPublic)}
          >
            <Globe 
              className={`w-5 h-5 ${isPublic ? 'text-primary-900' : 'text-greyscale-500'}`} 
            />
            <div className={`text-sm font-medium ${isPublic ? 'text-primary-900' : 'text-greyscale-500'}`}>
              {isPublic ? 'Public' : 'Private'}
            </div>
            <Switch
              className={`ml-1 relative shadow-[0px_1px_2px_#00000080] ${isPublic ? 'bg-primary-900' : 'bg-greyscale-300'}`}
              checked={isPublic}
              onCheckedChange={setIsPublic}
            />
          </div>
        </div>

        {/* Action buttons */}
        <div 
          className="absolute left-[23px] w-[382px]"
          style={{
            top: `${getContinueButtonPosition()}px`, 
          }}
        >
          <Button
            className="whitespace-nowrap text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 text-primary-foreground shadow hover:bg-primary/90 h-9 relative self-stretch w-full flex-[0_0_auto] bg-primary-900 shadow-button-shadow-1 flex items-center justify-center gap-2.5 px-4 py-[18px] rounded-[100px]"
            onClick={handleContinue}
            disabled={isCreating}
          >
            <span className="relative flex-1 mt-[-1.00px] font-body-xlarge-bold font-[number:var(--body-xlarge-bold-font-weight)] text-others-white text-[length:var(--body-xlarge-bold-font-size)] text-center tracking-[var(--body-xlarge-bold-letter-spacing)] leading-[var(--body-xlarge-bold-line-height)] [font-style:var(--body-xlarge-bold-font-style)]">
              {isCreating ? "Creating trip..." : "Continue"}
            </span>
          </Button>
        </div>
        
        {/* Error message if trip creation fails */}
        {error && (
          <div 
            className="absolute w-[382px] text-red-500 text-sm"
            style={{
              top: `${getContinueButtonPosition() + 60}px`, 
              left: "23px"
            }}
          >
            {error}
          </div>
        )}

        {/* Destination selection popover */}
        <ThemeProvider theme={theme}>
          <Popover
            open={Boolean(destinationAnchorEl)}
            anchorEl={destinationAnchorEl}
            onClose={handleDestinationMenuClose}
            anchorOrigin={{
              vertical: 'bottom',
              horizontal: 'center',
            }}
            transformOrigin={{
              vertical: 'top',
              horizontal: 'center',
            }}
            PaperProps={{
              style: {
                width: '300px',
                borderRadius: '16px',
                boxShadow: '0px 5px 15px rgba(0, 0, 0, 0.1)',
                marginTop: '8px',
                padding: '12px',
                maxHeight: '350px',
              },
            }}
          >
            <TextField
              autoFocus
              placeholder="Search cities"
              variant="outlined"
              fullWidth
              value={searchInput}
              onChange={handleSearchInputChange}
              sx={{ 
                mb: 1.5,
                '& .MuiOutlinedInput-root': {
                  borderRadius: '8px',
                }
              }}
              InputProps={{
                startAdornment: (
                  <span style={{ 
                    marginRight: '8px', 
                    color: '#666',
                    fontSize: '14px'
                  }}>
                    🔍
                  </span>
                )
              }}
            />
            <List sx={{ padding: '4px 0', maxHeight: '250px', overflow: 'auto' }}>
              {filteredCities.length > 0 ? (
                filteredCities.map((city) => (
                  <ListItem 
                    key={city} 
                    onClick={() => handleDestinationSelect(city)}
                    sx={{ 
                      cursor: 'pointer',
                      padding: '10px 12px',
                      borderRadius: '6px',
                      mb: 0.5,
                      '&:hover': {
                        backgroundColor: '#f5f8ff',
                      },
                      backgroundColor: selectedDestination === city ? '#e9efff' : 'transparent',
                      color: selectedDestination === city ? '#334FB8' : 'inherit',
                      fontWeight: selectedDestination === city ? 'bold' : 'normal',
                    }}
                  >
                    <ListItemText primary={city} />
                  </ListItem>
                ))
              ) : (
                <ListItem>
                  <ListItemText 
                    primary="No matching cities" 
                    primaryTypographyProps={{
                      style: {
                        fontStyle: 'italic',
                        color: '#999',
                        textAlign: 'center'
                      }
                    }}
                  />
                </ListItem>
              )}
            </List>
          </Popover>

          {/* Guest selection popover */}
          <Popover
            open={Boolean(guestAnchorEl)}
            anchorEl={guestAnchorEl}
            onClose={handleGuestMenuClose}
            anchorOrigin={{
              vertical: 'bottom',
              horizontal: 'center',
            }}
            transformOrigin={{
              vertical: 'top',
              horizontal: 'center',
            }}
            PaperProps={{
              style: {
                width: '250px',
                borderRadius: '16px',
                boxShadow: '0px 5px 15px rgba(0, 0, 0, 0.1)',
                marginTop: '8px',
                maxHeight: '300px',
              },
            }}
          >
            <List sx={{ padding: '8px 0' }}>
              {guestOptions.map((number) => (
                <ListItem 
                  key={number} 
                  onClick={() => handleGuestSelect(number)}
                  sx={{ 
                    cursor: 'pointer',
                    padding: '12px 16px',
                    borderBottom: number < guestOptions.length ? '1px solid #f0f0f0' : 'none',
                    backgroundColor: selectedGuests === number ? '#f5f8ff' : 'transparent',
                  }}
                >
                  <ListItemText 
                    primary={`${number} ${number === 1 ? 'Guest' : 'Guests'}`}
                    primaryTypographyProps={{
                      style: {
                        fontFamily: 'var(--body-large-regular-font-family)', 
                        fontSize: 'var(--body-large-regular-font-size)',
                        color: selectedGuests === number ? '#334FB8' : '#333333',
                        fontWeight: selectedGuests === number ? 'bold' : 'normal',
                      }
                    }}
                  />
                </ListItem>
              ))}
            </List>
          </Popover>

          {/* Budget selection popover */}
          <Popover
            open={Boolean(budgetAnchorEl)}
            anchorEl={budgetAnchorEl}
            onClose={handleBudgetMenuClose}
            anchorOrigin={{
              vertical: 'bottom',
              horizontal: 'center',
            }}
            transformOrigin={{
              vertical: 'top',
              horizontal: 'center',
            }}
            PaperProps={{
              style: {
                width: '250px',
                borderRadius: '16px',
                boxShadow: '0px 5px 15px rgba(0, 0, 0, 0.1)',
                marginTop: '8px',
              },
            }}
          >
            <List>
              {budgetOptions.map((option) => (
                <ListItem 
                  key={option.value} 
                  onClick={() => handleBudgetSelect(option.label)}
                  sx={{ 
                    cursor: 'pointer',
                    padding: '10px 16px',
                    '&:hover': {
                      backgroundColor: '#f5f8ff',
                    },
                    backgroundColor: selectedBudget === option.label ? '#e9efff' : 'transparent',
                    color: selectedBudget === option.label ? '#334FB8' : 'inherit',
                    fontWeight: selectedBudget === option.label ? 'bold' : 'normal',
                  }}
                >
                  <ListItemText primary={option.label} />
                </ListItem>
              ))}
            </List>
          </Popover>

          {/* Purpose selection popover */}
          <Popover
            open={Boolean(purposeAnchorEl)}
            anchorEl={purposeAnchorEl}
            onClose={handlePurposeMenuClose}
            anchorOrigin={{
              vertical: 'bottom',
              horizontal: 'center',
            }}
            transformOrigin={{
              vertical: 'top',
              horizontal: 'center',
            }}
            PaperProps={{
              style: {
                width: '300px',
                borderRadius: '16px',
                boxShadow: '0px 5px 15px rgba(0, 0, 0, 0.1)',
                marginTop: '8px',
                padding: '12px',
                maxHeight: '350px',
              },
            }}
          >
            <TextField
              autoFocus
              placeholder="Search or type your purpose"
              variant="outlined"
              fullWidth
              value={purposeInput}
              onChange={handlePurposeInputChange}
              sx={{ 
                mb: 1.5,
                '& .MuiOutlinedInput-root': {
                  borderRadius: '8px',
                }
              }}
              InputProps={{
                startAdornment: (
                  <span style={{ 
                    marginRight: '8px', 
                    color: '#666',
                    fontSize: '14px'
                  }}>
                    🔍
                  </span>
                )
              }}
            />
            <List sx={{ padding: '4px 0', maxHeight: '250px', overflow: 'auto' }}>
              {filteredPurposes.length > 0 ? (
                filteredPurposes.map((purpose) => (
                  <ListItem 
                    key={purpose} 
                    onClick={() => handlePurposeSelect(purpose)}
                    sx={{ 
                      cursor: 'pointer',
                      padding: '10px 12px',
                      borderRadius: '6px',
                      mb: 0.5,
                      '&:hover': {
                        backgroundColor: '#f5f8ff',
                      },
                      backgroundColor: selectedPurpose === purpose ? '#e9efff' : 'transparent',
                      color: selectedPurpose === purpose ? '#334FB8' : 'inherit',
                      fontWeight: selectedPurpose === purpose ? 'bold' : 'normal',
                    }}
                  >
                    <ListItemText primary={purpose} />
                  </ListItem>
                ))
              ) : (
                <ListItem 
                  onClick={() => handlePurposeSelect(purposeInput)}
                  sx={{ 
                    cursor: 'pointer',
                    padding: '10px 12px',
                    borderRadius: '6px',
                    mb: 0.5,
                    '&:hover': {
                      backgroundColor: '#f5f8ff',
                    }
                  }}
                >
                  <ListItemText 
                    primary={`Add "${purposeInput}" as custom purpose`}
                    primaryTypographyProps={{
                      style: {
                        color: '#334FB8',
                        fontStyle: 'italic'
                      }
                    }}
                  />
                </ListItem>
              )}
            </List>
          </Popover>

          {/* Calendar Dialog */}
          <Dialog
            open={showCalendar !== null}
            onClose={() => setShowCalendar(null)}
            PaperProps={{
              style: {
                borderRadius: '16px',
                padding: '0',
                maxWidth: '90%',
                width: '350px'
              }
            }}
          >
            <DialogTitle sx={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center',
              padding: '12px 16px'
            }}>
              <div style={{ fontWeight: 'bold' }}>
                {showCalendar === 'start' ? 'Start Date' : 'End Date'}
                <IconButton
                  onClick={() => setShowCalendar(null)}
                  sx={{ position: 'absolute', right: '8px', top: '8px' }}
                >
                  <CloseIcon size={18} />
                </IconButton>
              </div>
            </DialogTitle>
            <DialogContent sx={{ padding: '0 16px 16px' }}>
              {/* Month navigation */}
              <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center', 
                marginBottom: '8px' 
              }}>
                <div>{getMonthYearString()}</div>
                <div>
                  <IconButton onClick={goToPreviousMonth}>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className="text-[#00C29A]">
                      <path
                        d="M15 18L9 12L15 6"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </IconButton>
                  <IconButton onClick={goToNextMonth}>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className="text-[#00C29A]">
                      <path
                        d="M9 18L15 12L9 6"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </IconButton>
                </div>
              </div>
              
              {/* Calendar weekday headers */}
              <div style={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(7, 1fr)', 
                textAlign: 'center',
                marginBottom: '8px',
                fontWeight: 'bold' 
              }}>
                {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((day, index) => (
                  <div key={index} style={{ padding: '8px 0' }}>{day}</div>
                ))}
              </div>
              
              {/* Calendar days */}
              <div style={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(7, 1fr)', 
                gap: '2px' 
              }}>
                {generateCalendarDays().map((dateInfo, index) => (
                  <div
                    key={index}
                    onClick={() => dateInfo.isCurrentMonth && handleDayClick(dateInfo.year, dateInfo.month, dateInfo.day)}
                    style={{
                      padding: '8px 0',
                      textAlign: 'center',
                      cursor: dateInfo.isCurrentMonth ? 'pointer' : 'default',
                      color: isStartDate(dateInfo.day, dateInfo.month, dateInfo.year) ? 
                             'white' : 
                             isEndDate(dateInfo.day, dateInfo.month, dateInfo.year) ?
                             'white' :
                             isInRange(dateInfo.day, dateInfo.month, dateInfo.year) ?
                             '#1976d2' :
                             (dateInfo.isCurrentMonth ? 
                               (isToday(dateInfo.day, dateInfo.month, dateInfo.year) ? '#1976d2' : 'inherit') : 
                               '#aaa'),
                      backgroundColor: isStartDate(dateInfo.day, dateInfo.month, dateInfo.year) || 
                                      isEndDate(dateInfo.day, dateInfo.month, dateInfo.year) ? 
                                      '#1976d2' : 
                                      isInRange(dateInfo.day, dateInfo.month, dateInfo.year) ?
                                      '#e3f2fd' :
                                      'transparent',
                      borderRadius: '50%',
                      width: '36px',
                      height: '36px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      margin: '2px auto',
                      fontWeight: isToday(dateInfo.day, dateInfo.month, dateInfo.year) || 
                                  isStartDate(dateInfo.day, dateInfo.month, dateInfo.year) || 
                                  isEndDate(dateInfo.day, dateInfo.month, dateInfo.year) ? 
                                  'bold' : 'normal',
                      border: isToday(dateInfo.day, dateInfo.month, dateInfo.year) && 
                              !isSelected(dateInfo.day, dateInfo.month, dateInfo.year) ? 
                              '1px solid #1976d2' : 'none'
                    }}
                  >
                    {dateInfo.day}
                  </div>
                ))}
              </div>
              
              {/* Footer buttons */}
              <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                marginTop: '16px' 
              }}>
                <button
                  onClick={clearDateSelection}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#1976d2',
                    cursor: 'pointer',
                    fontSize: '14px'
                  }}
                >
                  Clear
                </button>
                <button
                  onClick={goToToday}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#1976d2',
                    cursor: 'pointer',
                    fontSize: '14px'
                  }}
                >
                  Today
                </button>
              </div>
            </DialogContent>
          </Dialog>
        </ThemeProvider>
      </div>
    </div>
  );
};

export default BuildANewTrip;
