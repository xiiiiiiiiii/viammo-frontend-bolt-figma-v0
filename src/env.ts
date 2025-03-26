// Environment configuration for the API
// This file centralizes environment-specific configuration

// Default values that can be overridden at runtime
const defaults = {
  apiHost: 'localhost',
  apiPort: '5001',
  apiPath: '/api'
};

// Get values from environment variables if available (for production deployment)
export const env = {
  // API host - can be overridden by VITE_API_HOST environment variable
  apiHost: import.meta.env.VITE_API_HOST || defaults.apiHost,
  
  // API port - can be overridden by VITE_API_PORT environment variable
  apiPort: import.meta.env.VITE_API_PORT || defaults.apiPort,
  
  // API path - can be overridden by VITE_API_PATH environment variable 
  apiPath: import.meta.env.VITE_API_PATH || defaults.apiPath,
  
  // Full API URL constructed from the components
  get apiUrl() {
    return `http://${this.apiHost}:${this.apiPort}${this.apiPath}`;
  }
};
