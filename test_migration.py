#!/usr/bin/env python3
"""
Test script for database migration
"""
import os
import sys
from app import app, db, check_and_migrate_schema, migrate_user_profile_table, migrate_food_entries_table
from sqlalchemy import text
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_database_connection():
    """Test basic database connection"""
    try:
        with app.app_context():
            result = db.session.execute(text('SELECT 1'))
            logging.info("✅ Database connection successful")
            return True
    except Exception as e:
        logging.error(f"❌ Database connection failed: {str(e)}")
        return False

def check_table_schema(table_name, required_columns):
    """Check if a table has all required columns"""
    try:
        with app.app_context():
            # Check if table exists
            table_check = db.session.execute(text(
                f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table_name}')"
            ))
            table_exists = table_check.scalar()
            logging.info(f"{table_name} table exists: {table_exists}")
            
            if table_exists:
                # Check columns
                columns_result = db.session.execute(text(
                    f"SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name='{table_name}' ORDER BY column_name"
                ))
                columns = columns_result.fetchall()
                
                logging.info(f"{table_name} table columns:")
                existing_columns = set()
                for col in columns:
                    logging.info(f"  - {col[0]}: {col[1]} (nullable: {col[2]})")
                    existing_columns.add(col[0])
                
                # Check for required columns
                missing_columns = set(required_columns) - existing_columns
                if missing_columns:
                    logging.warning(f"Missing columns in {table_name}: {missing_columns}")
                    return False
                else:
                    logging.info(f"✅ All required columns present in {table_name}")
                    return True
            else:
                logging.warning(f"{table_name} table does not exist")
                return False
                
    except Exception as e:
        logging.error(f"Schema check failed for {table_name}: {str(e)}")
        return False

def run_migration_test():
    """Run migration and test"""
    try:
        with app.app_context():
            logging.info("🔄 Starting comprehensive migration test...")
            
            # Define required columns for each table
            required_schemas = {
                'users': ['id', 'username', 'password_hash', 'created_at'],
                'food_entries': ['id', 'user_id', 'product_id', 'weight', 'date', 'meal_type', 'created_at'],
                'user_profile': ['id', 'user_id', 'name', 'age', 'gender', 'weight', 'height', 'activity_level', 'goal', 'target_calories', 'created_at']
            }
            
            # Check schema before migration
            logging.info("📋 Checking schemas before migration:")
            before_status = {}
            for table, columns in required_schemas.items():
                before_status[table] = check_table_schema(table, columns)
            
            # Run migration
            logging.info("🚀 Running comprehensive migration...")
            migration_result = check_and_migrate_schema()
            
            if migration_result:
                logging.info("✅ Migration completed successfully")
            else:
                logging.warning("⚠️  Migration returned False (might not be needed)")
            
            # Check schema after migration
            logging.info("📋 Checking schemas after migration:")
            after_status = {}
            for table, columns in required_schemas.items():
                after_status[table] = check_table_schema(table, columns)
            
            # Report results
            all_good = all(after_status.values())
            if all_good:
                logging.info("✅ All table schemas are now correct!")
                return True
            else:
                failed_tables = [table for table, status in after_status.items() if not status]
                logging.error(f"❌ Some table schemas are still incorrect: {failed_tables}")
                return False
                
    except Exception as e:
        logging.error(f"❌ Migration test failed: {str(e)}")
        return False

def main():
    """Main test function"""
    logging.info("🧪 Starting comprehensive database migration test")
    
    # Test 1: Database connection
    if not test_database_connection():
        logging.error("Cannot proceed without database connection")
        return False
    
    # Test 2: Run migration
    if not run_migration_test():
        logging.error("Migration test failed")
        return False
    
    logging.info("🎉 All tests passed!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)