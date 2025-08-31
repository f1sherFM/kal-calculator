#!/usr/bin/env python3
"""
Test script for database migration
"""
import os
import sys
from app import app, db, check_and_migrate_schema, migrate_user_profile_table
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

def check_user_profile_schema():
    """Check user_profile table schema"""
    try:
        with app.app_context():
            # Check if table exists
            table_check = db.session.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'user_profile')"
            ))
            table_exists = table_check.scalar()
            logging.info(f"user_profile table exists: {table_exists}")
            
            if table_exists:
                # Check columns
                columns_result = db.session.execute(text(
                    "SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name='user_profile' ORDER BY column_name"
                ))
                columns = columns_result.fetchall()
                
                logging.info("user_profile table columns:")
                for col in columns:
                    logging.info(f"  - {col[0]}: {col[1]} (nullable: {col[2]})")
                
                # Specifically check for user_id column
                user_id_exists = any(col[0] == 'user_id' for col in columns)
                logging.info(f"user_id column exists: {user_id_exists}")
                
                return user_id_exists
            else:
                logging.warning("user_profile table does not exist")
                return False
                
    except Exception as e:
        logging.error(f"Schema check failed: {str(e)}")
        return False

def run_migration_test():
    """Run migration and test"""
    try:
        with app.app_context():
            logging.info("🔄 Starting migration test...")
            
            # Check schema before migration
            logging.info("📋 Checking schema before migration:")
            before_status = check_user_profile_schema()
            
            # Run migration
            logging.info("🚀 Running migration...")
            migration_result = check_and_migrate_schema()
            
            if migration_result:
                logging.info("✅ Migration completed successfully")
            else:
                logging.warning("⚠️  Migration returned False (might not be needed)")
            
            # Check schema after migration
            logging.info("📋 Checking schema after migration:")
            after_status = check_user_profile_schema()
            
            if after_status:
                logging.info("✅ user_profile schema is now correct!")
                return True
            else:
                logging.error("❌ user_profile schema is still incorrect after migration")
                return False
                
    except Exception as e:
        logging.error(f"❌ Migration test failed: {str(e)}")
        return False

def main():
    """Main test function"""
    logging.info("🧪 Starting database migration test")
    
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