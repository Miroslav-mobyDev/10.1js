#!/usr/bin/env python3
"""
Setup script for Telegram Marathon Registration Bot
"""

import os
import sys

def create_env_file():
    """Create .env file from template if it doesn't exist"""
    if os.path.exists('.env'):
        print("✅ .env file already exists")
        return
    
    if not os.path.exists('.env.example'):
        print("❌ .env.example file not found")
        return
    
    # Copy example to .env
    with open('.env.example', 'r') as source:
        content = source.read()
    
    with open('.env', 'w') as target:
        target.write(content)
    
    print("✅ Created .env file from template")
    print("📝 Please edit .env file with your actual bot credentials")

def check_dependencies():
    """Check if required packages are installed"""
    required_packages = [
        'telegram',
        'python-dotenv'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing packages: {', '.join(missing_packages)}")
        print("📦 Install them with: pip install -r requirements.txt")
        return False
    else:
        print("✅ All required packages are installed")
        return True

def validate_env_file():
    """Validate .env file configuration"""
    if not os.path.exists('.env'):
        print("❌ .env file not found. Run setup first.")
        return False
    
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = ['BOT_TOKEN', 'ADMIN_ID', 'WHATSAPP_GROUP_LINK']
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if not value or value.startswith('your_') or value == '123456789':
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Please configure these variables in .env file: {', '.join(missing_vars)}")
        return False
    else:
        print("✅ .env configuration looks good")
        return True

def main():
    """Main setup function"""
    print("🤖 Telegram Marathon Registration Bot Setup")
    print("=" * 50)
    
    # Step 1: Create .env file
    print("\n1. Creating configuration file...")
    create_env_file()
    
    # Step 2: Check dependencies
    print("\n2. Checking dependencies...")
    if not check_dependencies():
        print("\n❌ Setup incomplete. Install dependencies first.")
        sys.exit(1)
    
    # Step 3: Validate configuration
    print("\n3. Validating configuration...")
    if not validate_env_file():
        print("\n❌ Setup incomplete. Configure .env file first.")
        print("\nNext steps:")
        print("1. Edit .env file with your bot token, admin ID, and WhatsApp link")
        print("2. Run this setup script again to validate")
        print("3. Start the bot with: python improved_telegram_bot.py")
        sys.exit(1)
    
    # All good!
    print("\n🎉 Setup completed successfully!")
    print("\nYou can now start the bot with:")
    print("  python improved_telegram_bot.py")
    print("\nAdmin commands:")
    print("  /stats - Get registration statistics")
    print("\nUser flow:")
    print("  /start - Begin registration process")

if __name__ == "__main__":
    main()