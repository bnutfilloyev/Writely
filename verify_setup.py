#!/usr/bin/env python3
"""
Verification script to check project structure setup.
"""
import os
import sys

def check_directory_structure():
    """Check if all required directories exist."""
    required_dirs = [
        'src',
        'src/config',
        'src/models', 
        'src/services',
        'src/handlers',
        'src/database',
        'tests'
    ]
    
    missing_dirs = []
    for directory in required_dirs:
        if not os.path.exists(directory):
            missing_dirs.append(directory)
    
    return missing_dirs

def check_required_files():
    """Check if all required files exist."""
    required_files = [
        'main.py',
        'requirements.txt',
        'setup.sh',
        '.env.example',
        '.gitignore',
        'src/__init__.py',
        'src/config/__init__.py',
        'src/config/settings.py',
        'src/models/__init__.py',
        'src/services/__init__.py',
        'src/handlers/__init__.py',
        'src/database/__init__.py',
        'tests/__init__.py'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    return missing_files

def main():
    """Run verification checks."""
    print("🔍 Verifying project structure setup...")
    
    # Check directories
    missing_dirs = check_directory_structure()
    if missing_dirs:
        print(f"❌ Missing directories: {', '.join(missing_dirs)}")
        return False
    else:
        print("✅ All required directories exist")
    
    # Check files
    missing_files = check_required_files()
    if missing_files:
        print(f"❌ Missing files: {', '.join(missing_files)}")
        return False
    else:
        print("✅ All required files exist")
    
    # Check requirements.txt content
    try:
        with open('requirements.txt', 'r') as f:
            requirements = f.read()
            required_packages = ['aiogram', 'openai', 'sqlalchemy', 'fastapi', 'python-dotenv']
            missing_packages = []
            for package in required_packages:
                if package not in requirements:
                    missing_packages.append(package)
            
            if missing_packages:
                print(f"❌ Missing packages in requirements.txt: {', '.join(missing_packages)}")
                return False
            else:
                print("✅ All required packages listed in requirements.txt")
    except FileNotFoundError:
        print("❌ requirements.txt not found")
        return False
    
    # Check .env.example
    try:
        with open('.env.example', 'r') as f:
            env_content = f.read()
            required_vars = ['TELEGRAM_BOT_TOKEN', 'OPENAI_API_KEY', 'DATABASE_URL']
            missing_vars = []
            for var in required_vars:
                if var not in env_content:
                    missing_vars.append(var)
            
            if missing_vars:
                print(f"❌ Missing environment variables in .env.example: {', '.join(missing_vars)}")
                return False
            else:
                print("✅ All required environment variables in .env.example")
    except FileNotFoundError:
        print("❌ .env.example not found")
        return False
    
    print("\n🎉 Project structure setup completed successfully!")
    print("\nNext steps:")
    print("1. Run './setup.sh' to create virtual environment and install dependencies")
    print("2. Copy '.env.example' to '.env' and fill in your API keys")
    print("3. Proceed to implement the next task in the implementation plan")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)