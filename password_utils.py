#!/usr/bin/env python3
"""
Password utility functions for generating and hashing passwords.
"""

import secrets
import string
import bcrypt


def generate_secure_password(length=16):
    """
    Generate a secure random password with:
    - Uppercase letters
    - Lowercase letters
    - Digits
    - Special characters
    
    Args:
        length (int): Length of the password (default: 16)
    
    Returns:
        str: Generated secure password
    """
    # Define character sets
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    special = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    
    # Ensure at least one character from each category
    password_chars = [
        secrets.choice(uppercase),
        secrets.choice(lowercase),
        secrets.choice(digits),
        secrets.choice(special)
    ]
    
    # Fill the rest with random characters from all sets
    all_chars = uppercase + lowercase + digits + special
    for _ in range(length - 4):
        password_chars.append(secrets.choice(all_chars))
    
    # Shuffle to avoid predictable pattern
    secrets.SystemRandom().shuffle(password_chars)
    
    return ''.join(password_chars)


def hash_password(password):
    """
    Hash password using bcrypt (same as n8n uses).
    
    Args:
        password (str): Plain text password to hash
    
    Returns:
        str: Hashed password
    """
    # n8n uses bcrypt with salt rounds 10
    salt = bcrypt.gensalt(rounds=10)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

