# Database Schema Migration Fix

## Problem
The application was experiencing errors because the database schema was missing critical columns:

1. **user_profile.user_id** column was missing, causing:
   ```
   psycopg.errors.UndefinedColumn: column user_profile.user_id does not exist
   ```

2. **food_entries.user_id** column was missing, causing:
   ```
   psycopg.errors.UndefinedColumn: column food_entries.user_id does not exist
   ```

## Root Cause
The database was created from an earlier version of the schema before user authentication was implemented. The tables existed but were missing the foreign key columns needed for multi-user functionality.

## Solution Implemented

### 1. Comprehensive Migration System
Created a robust migration system that includes:

- **`migrate_food_entries_table()`**: Adds missing user_id column to food_entries table
- **`migrate_user_profile_table()`**: Adds missing user_id column to user_profile table  
- **`check_and_migrate_schema()`**: Orchestrates all migrations
- **`ensure_tables_exist()`**: Creates tables if they don't exist

### 2. Data Preservation Strategy
The migration system preserves existing data by:

- Checking for existing records before adding constraints
- Assigning existing records to the first available user
- Creating a default admin user if no users exist
- Adding NOT NULL constraints only after data migration
- Adding foreign key constraints with error handling

### 3. Manual Migration Endpoints
Created debugging and manual migration routes:

- **`/check_schema`**: JSON API to check current schema status
- **`/migrate_all`**: Comprehensive migration for all tables
- **`/migrate_food_entries`**: Specific migration for food_entries table
- **`/migrate_user_profile`**: Specific migration for user_profile table

### 4. Automatic Migration on Startup
The migration runs automatically when the application starts:

```python
# During app initialization
with app.app_context():
    init_database()
    check_and_migrate_schema()
```

### 5. Route-Level Migration Checks
Added migration checks in critical routes with error handling:

```python
try:
    check_and_migrate_schema()
except Exception as migration_error:
    logging.warning(f"Migration check failed, continuing anyway: {migration_error}")
```

## Database Schema After Migration

### food_entries table
```sql
- id (PRIMARY KEY)
- user_id (FOREIGN KEY to users.id, NOT NULL) ← ADDED
- product_id (FOREIGN KEY to products.id)
- weight (FLOAT)
- date (DATE)
- meal_type (VARCHAR)
- created_at (TIMESTAMP)
```

### user_profile table
```sql
- id (PRIMARY KEY)
- user_id (FOREIGN KEY to users.id, NOT NULL, UNIQUE) ← ADDED
- name (VARCHAR)
- age (INTEGER)
- gender (VARCHAR)
- weight (FLOAT)
- height (FLOAT)
- activity_level (VARCHAR)
- goal (VARCHAR)
- target_calories (INTEGER)
- created_at (TIMESTAMP)
```

## Testing and Verification

### Schema Status Check
```bash
curl http://localhost:5000/check_schema
```

Returns:
```json
{
  "status": "ok",
  "details": {
    "food_entries_table_exists": true,
    "food_entries_user_id_exists": true,
    "user_profile_table_exists": true,
    "user_profile_user_id_exists": true,
    "food_entries_count": 0,
    "user_profile_count": 1
  }
}
```

### Application Logs
```
2025-08-31 08:39:48 - INFO - Starting food_entries table migration...
2025-08-31 08:39:48 - INFO - user_id column missing in food_entries, adding it...
2025-08-31 08:39:48 - INFO - user_id column added to food_entries successfully
2025-08-31 08:39:48 - INFO - user_profile table already has user_id column
2025-08-31 08:39:48 - INFO - Schema check completed successfully
```

## Files Modified

- **`app.py`**: Added comprehensive migration functions and routes
- **`test_migration.py`**: Created test script for migration verification

## Error Resolution Status

✅ **RESOLVED**: `column user_profile.user_id does not exist`
✅ **RESOLVED**: `column food_entries.user_id does not exist`  
✅ **RESOLVED**: Application context issues during startup
✅ **TESTED**: All routes now work correctly
✅ **VERIFIED**: Database schema is complete and consistent

## Future Maintenance

The migration system is designed to be:
- **Idempotent**: Can be run multiple times safely
- **Data-safe**: Preserves existing data during migrations
- **Logged**: Provides detailed logging for debugging
- **Testable**: Includes comprehensive test scripts
- **Manual**: Provides manual endpoints for troubleshooting

The application will now automatically handle schema updates on startup, ensuring database consistency across deployments.