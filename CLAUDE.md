# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

pibiDAV is a Frappe App that integrates WebDAV functionality with NextCloud Server, enabling automatic file synchronization between Frappe and NextCloud. When files are uploaded to Frappe, they are simultaneously uploaded to NextCloud with automatic tagging and folder organization.

## Development Commands

### Build Commands
```bash
# Build JavaScript and CSS assets for the pibidav app
bench build --app pibidav

# Build in production mode (minified)
bench build --app pibidav --production

# Force rebuild instead of downloading available assets
bench build --app pibidav --force
```

### Test Commands
```bash
# Run all tests for pibidav app
bench run-tests --app pibidav

# Run tests for specific doctype
bench run-tests --app pibidav --doctype "NextCloud Settings"

# Run tests with coverage
bench run-tests --app pibidav --coverage

# Run UI tests
bench run-ui-tests
```

### Database and Migration
```bash
# Run patches and sync schema after code changes
bench migrate

# Clear cache after making changes
bench clear-cache
```

### Installation
```bash
# Install the app to a site
bench --site site_name install-app pibidav

# Get the app from repository
bench get-app pibidav --branch version-15 https://github.com/pibico/pibidav.git
```

## Architecture Overview

### Backend Architecture

1. **Frappe Integration via hooks.py**
   - Dynamically injects JavaScript into configured doctypes (Customer, Sales Invoice, etc.)
   - Hooks into File doctype's after_insert event for automatic NextCloud upload
   - Scheduled tasks for daily/weekly backups to NextCloud
   - Defines app-level JavaScript bundles and icons

2. **Core Module Structure**
   - `pibidav/nextcloud.py`: Main NextCloud API integration using embedded pyocclient
   - `pibidav/custom.py`: Custom functions for file operations and folder management
   - DocTypes for configuration and data storage:
     - `NextCloud Settings`: Global configuration and credentials
     - `PibiDAV Addon`: Extension data for integrated doctypes
     - `Folder Set`: Template-based folder structure creation

3. **Integration Pattern**
   - Each integrated doctype gets a parallel "addon" document (prefixed with 'pbc_')
   - Addons store NextCloud-specific data (folder paths, references, attachments)
   - File uploads trigger automatic NextCloud synchronization with tagging

### Frontend Architecture

1. **JavaScript Module System**
   - `nc_pibidav.js`: Main form integration that adds NextCloud buttons to doctypes
   - `nc_browser.bundle.js`: Vue 3 application for folder browsing and selection
   - Lazy-loaded components for optimal performance

2. **Vue.js Components**
   - `NcBrowser.vue`: Main file browser with tree navigation
   - `TreeNode.vue`: Recursive component for folder tree rendering
   - Uses Vue 3 composition API with TypeScript support

3. **API Integration**
   - Server calls via `frappe.call()` for NextCloud operations
   - Real-time folder browsing and file listing
   - Folder creation with template support

### Key Integration Points

1. **Authentication Flow**
   - SuperUser credentials stored in NextCloud Settings
   - Per-user credentials stored in User doctype with "NextCloud User" role
   - Automatic credential validation and connection testing

2. **File Upload Pipeline**
   - File uploaded to Frappe → triggers `after_insert` hook
   - Checks if parent doctype is NC-enabled
   - Uploads to selected NextCloud folder with automatic tagging
   - Creates public share links automatically

3. **Folder Structure Management**
   - Template-based folder creation using Folder Set doctype
   - Recursive folder structure replication in NextCloud
   - Automatic folder naming with abbreviations and descriptions

## Important Implementation Details

1. **SSL Requirements**: Both Frappe and NextCloud must have valid SSL certificates (wildcard certificates not supported)

2. **Developer Mode**: Requires `developer_mode = 1` in site_config.json

3. **Tagging System**: Files are automatically tagged based on configured doctype fields (e.g., customer name, tax_id)

4. **Backup Integration**: Automatic daily/weekly backups to NextCloud with version control

5. **Error Handling**: Graceful fallback if NextCloud is unreachable - files still save to Frappe

6. **Performance**: Uses lazy loading and caching for optimal performance with large folder structures