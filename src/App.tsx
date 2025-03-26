import React from 'react';
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import { Trips } from './screens/Trips/Trips';
import { BuildANewTrip } from './screens/BuildANewTrip';
import TripDraftCalendar from './screens/TripDraftCalendar/TripDraftCalendar';
import { TripElementDetail } from './screens/TripElementDetail/TripElementDetail';
import { TripProvider } from './contexts/TripContext';
import TestScreen from './screens/TestScreen';

const App: React.FC = () => {
  return (
    <Router>
      <TripProvider>
        <Routes>
          <Route path="/" element={<Trips />} />
          <Route path="/trips" element={<Trips />} />
          <Route path="/build-new-trip/:id" element={<BuildANewTrip />} />
          <Route path="/trip-draft-calendar" element={<TripDraftCalendar />} />
          <Route path="/trip-draft-calendar/:id" element={<TripDraftCalendar />} />
          <Route path="/trip-element-detail/:id?" element={<TripElementDetail />} />
          <Route path="/test" element={<TestScreen />} />
        </Routes>
      </TripProvider>
    </Router>
  );
};

export default App;
