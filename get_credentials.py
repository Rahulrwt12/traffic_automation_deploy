#!/usr/bin/env python3
"""
Helper script to configure credentials for HTTP Basic Authentication
"""

import json
import os
import getpass
import sys

def get_credentials():
    """Interactive credential setup"""
    print("="*60)
    print("🔐 HTTP Basic Authentication Setup")
    print("="*60)
    print()
    print("This script will help you configure credentials for")
    print("www-qa.advancedenergy.com")
    print()
    print("⚠️  You need to get these credentials from:")
    print("   - Your system administrator")
    print("   - Your QA environment team")
    print("   - Your project documentation")
    print()
    
    # Check if config exists
    config_file = 'config.json'
    if not os.path.exists(config_file):
        print(f"❌ Error: {config_file} not found!")
        return
    
    # Load config
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Error reading config: {e}")
        return
    
    # Get credentials
    print("Enter your credentials:")
    print()
    
    username = input("Username: ").strip()
    if not username:
        print("❌ Username cannot be empty!")
        return
    
    password = getpass.getpass("Password: ").strip()
    if not password:
        print("❌ Password cannot be empty!")
        return
    
    # Confirm
    print()
    confirm = input(f"Set credentials for domain '{config.get('target_domain', 'www-qa.advancedenergy.com')}'? (y/n): ").strip().lower()
    if confirm != 'y':
        print("❌ Cancelled.")
        return
    
    # Update config
    if 'browser' not in config:
        config['browser'] = {}
    
    if 'authentication' not in config['browser']:
        config['browser']['authentication'] = {}
    
    config['browser']['authentication']['enabled'] = True
    config['browser']['authentication']['username'] = username
    config['browser']['authentication']['password'] = password
    config['browser']['authentication']['domain'] = config.get('target_domain', 'www-qa.advancedenergy.com')
    
    # Save config
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        print()
        print("✅ Credentials saved successfully!")
        print()
        print("⚠️  Security Note:")
        print("   Your credentials are stored in plain text in config.json")
        print("   Do NOT commit this file to version control!")
        print()
        print("You can now run: python3 traffic_bot.py")
    except Exception as e:
        print(f"❌ Error saving config: {e}")

if __name__ == '__main__':
    try:
        get_credentials()
    except KeyboardInterrupt:
        print("\n❌ Cancelled by user.")
        sys.exit(1)

