# MongoDB Credential Management

This directory contains scripts for securely managing MongoDB credentials using environment variables and generating configuration files for the application to use.

## Security Best Practices

1. **Never hardcode credentials** in your code or commit them to version control
2. Store sensitive information in environment variables or secure credential files
3. Use `.gitignore` to exclude credential files from version control
4. For production, use a secure secrets management service

## Setup Instructions

### 1. Add Environment Variables

Edit the `.env` file and add your MongoDB credentials:

```
MONGODB_USERNAME=your_username
MONGODB_PASSWORD=your_password
MONGODB_CLUSTER=your_cluster.mongodb.net
MONGODB_DATABASE=your_database
MONGODB_DATASOURCE=your_datasource
```

## API Server

The MongoDB API server provides a secure way to access MongoDB data without exposing credentials in the frontend code.

### Starting the API Server

```bash
python backend/mongo_api_server.py --port 5001
```

Optional parameters:
- `--port PORT`: Specify port to run the server on (default: 5001)
- `--debug`: Run in debug mode

### API Endpoints

- `GET /api/health`: API health check
- `GET /api/trips`: Get all trips
- `GET /api/trips/:id`: Get a specific trip
- `GET /api/calendar/:tripId`: Get calendar items for a specific trip

## For Production Deployment

For production environments:

1. **Use environment variables** on your server instead of `.env` files
2. Configure a proper backend service that securely handles MongoDB connections
3. Consider using a secrets management service like AWS Secrets Manager, HashiCorp Vault, or similar
4. Implement proper authentication and authorization for your API
5. Use HTTPS for all API communication

## Troubleshooting

- If you see an error about missing environment variables, ensure your `.env` file contains all required variables
- If the API server fails to connect to MongoDB, check your credentials and network connectivity
- If port 5001 is already in use, specify a different port using the `--port` parameter
