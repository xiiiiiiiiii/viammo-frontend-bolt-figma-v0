import React from 'react';
import { useNavigate } from 'react-router-dom';

const TestScreen: React.FC = () => {
  const navigate = useNavigate();
  
  return (
    <div className="max-w-md mx-auto h-screen bg-white p-6">
      <h1 className="text-xl font-bold mb-4">Test Screen</h1>
      <p className="mb-4">This is a simple test screen to verify that the React router and component rendering is working correctly.</p>
      <button 
        className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded mb-4 block w-full"
        onClick={() => navigate('/trips')}
      >
        Back to Trips
      </button>
      <div className="p-4 border border-gray-200 rounded">
        <h2 className="font-bold mb-2">Debug Information</h2>
        <p>React Router is functioning if you can see this screen and use the button above.</p>
      </div>
    </div>
  );
};

export default TestScreen;
