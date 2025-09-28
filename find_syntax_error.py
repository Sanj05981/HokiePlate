#!/usr/bin/env python3
"""
Script to help find syntax errors in Python files
"""

import ast
import sys

def find_syntax_error(filename):
    """Find and display syntax errors in a Python file"""
    
    print(f"Checking syntax in {filename}...")
    
    try:
        with open(filename, 'r') as f:
            content = f.read()
        
        # Try to parse the file
        ast.parse(content)
        print("✅ No syntax errors found!")
        return True
        
    except FileNotFoundError:
        print(f"❌ File {filename} not found")
        return False
        
    except SyntaxError as e:
        print(f"❌ Syntax Error Found!")
        print(f"   Line {e.lineno}: {e.text.strip() if e.text else 'Unknown'}")
        print(f"   Error: {e.msg}")
        print(f"   Position: {' ' * (e.offset - 1) if e.offset else ''}^")
        
        # Show context around the error
        lines = content.split('\n')
        start = max(0, e.lineno - 3)
        end = min(len(lines), e.lineno + 2)
        
        print(f"\nContext around line {e.lineno}:")
        for i in range(start, end):
            marker = ">>> " if i == e.lineno - 1 else "    "
            print(f"{marker}{i+1:3}: {lines[i]}")
        
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def check_common_issues(filename):
    """Check for common syntax issues"""
    
    try:
        with open(filename, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        return
    
    print(f"\nChecking common issues in {filename}:")
    
    # Check for unmatched brackets
    open_brackets = {'(': 0, '[': 0, '{': 0}
    
    for line_num, line in enumerate(lines, 1):
        for char in line:
            if char in '([{':
                open_brackets[char] += 1
            elif char in ')]}':
                corresponding = {')': '(', ']': '[', '}': '{'}
                if open_brackets[corresponding[char]] > 0:
                    open_brackets[corresponding[char]] -= 1
                else:
                    print(f"❌ Line {line_num}: Unmatched closing '{char}'")
    
    # Check for unmatched opening brackets
    for bracket, count in open_brackets.items():
        if count > 0:
            print(f"❌ {count} unmatched opening '{bracket}' bracket(s)")
    
    # Check last few lines for incomplete statements
    last_lines = lines[-5:] if len(lines) >= 5 else lines
    
    print(f"\nLast {len(last_lines)} lines of file:")
    start_line = len(lines) - len(last_lines) + 1
    for i, line in enumerate(last_lines):
        print(f"    {start_line + i:3}: {line.rstrip()}")

if __name__ == "__main__":
    filename = "app1.py"
    
    print("=== Python Syntax Error Checker ===\n")
    
    # Check syntax
    is_valid = find_syntax_error(filename)
    
    if not is_valid:
        check_common_issues(filename)
        
        print(f"\n=== How to Fix ===")
        print("1. Look at the error line and surrounding context")
        print("2. Check for missing closing brackets: ), ], }")
        print("3. Check for missing colons after if/def/for/while statements")
        print("4. Check for unclosed strings (missing quotes)")
        print("5. Make sure function definitions are complete")
    
    print(f"\n=== Quick Fix Options ===")
    print("Option 1: Use the clean app.py file I provided earlier")
    print("Option 2: Copy your changes to a new file")
    print("Option 3: Fix the specific syntax error above")