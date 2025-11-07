#!/usr/bin/env python3
"""
Setup script for Traffic Bot
Installs Python dependencies and Playwright Firefox browser automatically
"""

import subprocess
import sys
import os

def run_command(command, description, check=True):
    """Run a shell command and handle errors"""
    print(f"\n{'='*50}")
    print(f"📦 {description}")
    print('='*50)
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=check,
            capture_output=False,
            text=True
        )
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {description} failed")
        print(f"   Return code: {e.returncode}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error during {description}: {e}")
        return False

def main():
    print("="*50)
    print("🚀 Traffic Bot Setup")
    print("="*50)
    
    # Step 1: Install Python dependencies
    pip_cmd = "pip3" if sys.platform != "win32" else "pip"
    
    # Check if we're in a virtual environment
    in_venv = hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )
    
    if in_venv:
        pip_cmd = f"{sys.executable} -m pip"
        print(f"✅ Detected virtual environment: {sys.prefix}")
    
    print(f"\nUsing pip command: {pip_cmd}")
    
    if not run_command(
        f"{pip_cmd} install -r requirements.txt",
        "Installing Python dependencies"
    ):
        print("\n❌ Failed to install Python dependencies")
        print("   Please check your pip installation and try again")
        sys.exit(1)
    
    print("\n✅ Python dependencies installed successfully!")
    
    # Step 2: Install Playwright Firefox browser
    # Try different methods to run playwright install
    playwright_methods = [
        ("playwright install firefox", "Using playwright command"),
        (f"{sys.executable} -m playwright install firefox", "Using python -m playwright"),
    ]
    
    firefox_installed = False
    for cmd, method in playwright_methods:
        print(f"\n🌐 Attempting Firefox installation: {method}")
        if run_command(cmd, f"Installing Firefox browser ({method})", check=False):
            firefox_installed = True
            break
    
    if not firefox_installed:
        print("\n❌ Failed to install Firefox browser")
        print("\nPlease try manually:")
        print("   playwright install firefox")
        print("   OR")
        print("   python3 -m playwright install firefox")
        sys.exit(1)
    
    print("\n✅ Firefox browser installed successfully!")
    
    # Step 3: Check for credentials
    print("\n" + "="*50)
    print("🔐 Authentication Setup")
    print("="*50)
    
    config_file = 'config.json'
    if os.path.exists(config_file):
        import json
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            auth_config = config.get('browser', {}).get('authentication', {})
            auth_enabled = auth_config.get('enabled', False)
            auth_username = auth_config.get('username', '')
            auth_password = auth_config.get('password', '')
            
            target_domain = config.get('target_domain', 'www-qa.advancedenergy.com')
            
            # Check if credentials are needed
            if 'qa' in target_domain.lower() or 'advancedenergy' in target_domain.lower():
                print(f"\n⚠️  IMPORTANT: The target domain '{target_domain}' requires authentication!")
                print("   Without credentials, the bot will fail with ERR_INVALID_AUTH_CREDENTIALS errors.")
                print()
                
                if not auth_enabled or not auth_username or not auth_password:
                    print("❌ Authentication is not configured or credentials are missing.")
                    print()
                    response = input("Would you like to configure credentials now? (y/n): ").strip().lower()
                    
                    if response == 'y':
                        print("\n🔐 Running credential setup script...")
                        print()
                        try:
                            # Import and run get_credentials
                            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                            from get_credentials import get_credentials
                            get_credentials()
                        except Exception as e:
                            print(f"\n❌ Error running credential setup: {e}")
                            print("\nYou can set up credentials manually:")
                            print("  1. Run: python3 get_credentials.py")
                            print("  2. Or edit config.json → browser.authentication")
                    else:
                        print("\n⚠️  Skipping credential setup.")
                        print("   Remember to configure credentials before running the bot!")
                        print("   Run: python3 get_credentials.py")
                else:
                    print(f"✅ Authentication is already configured for user: {auth_username}")
            else:
                print("ℹ️  Authentication may not be required for this domain.")
                print("   You can configure it later if needed: python3 get_credentials.py")
        except Exception as e:
            print(f"\n⚠️  Could not check config file: {e}")
            print("   You can configure credentials later: python3 get_credentials.py")
    else:
        print("\n⚠️  config.json not found. It will be created when you run traffic_bot.py")
        print("   You can configure credentials after: python3 get_credentials.py")
    
    # Success message
    print("\n" + "="*50)
    print("✅ Setup completed successfully!")
    print("="*50)
    print("\nNext steps:")
    print("  1. Configure credentials (if needed): python3 get_credentials.py")
    print("  2. Run the bot: python3 traffic_bot.py")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

