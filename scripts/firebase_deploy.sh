#!/bin/bash

# This script assumes you want to set up a default database in a new project for testing

# Ensure you have the Firebase CLI installed and authenticated
# Install: npm install -g firebase-tools
# Authenticate: firebase login

# Variables
PROJECT_ID="new-project-id"
PROJECT_NAME="New Project Name"
INDEX_FILE="firestore.indexes.json"

# Create a new project
firebase projects:create $PROJECT_ID --display-name "$PROJECT_NAME"

# Set the project context temporarily
firebase use --add $PROJECT_ID

# Deploy Firestore indexes
firebase deploy --only firestore:indexes --project $PROJECT_ID
