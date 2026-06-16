from pathlib import Path
from ctx_finder.parser import parse_python_file, parse_regex_file, parse_file

def test_parse_python_file():
    code = """
import os
from sys import path

@router.get("/login")
def login_handler():
    pass

class AuthManager:
    @classmethod
    def get_session(cls):
        pass
"""
    symbols, imports = parse_python_file(code, "test_file.py")
    
    assert "os" in imports
    assert "sys" in imports
    
    classes = [s.name for s in symbols if s.symbol_type == "class"]
    functions = [s.name for s in symbols if s.symbol_type == "function"]
    methods = [s.name for s in symbols if s.symbol_type == "method"]
    routes = [s.name for s in symbols if s.symbol_type == "route"]
    
    assert "AuthManager" in classes
    assert "login_handler" in functions
    assert "get_session" in methods
    assert "login_handler route" in routes

def test_parse_js_file():
    code = """
import { session } from './session';
const auth = require('auth-lib');

class UserProfile {
    constructor() {}
}

export const loadProfile = async () => {};
function deleteUser() {}
"""
    symbols, imports = parse_regex_file(code, "javascript", "test_file.js")
    
    assert "./session" in imports
    assert "auth-lib" in imports
    
    classes = [s.name for s in symbols if s.symbol_type == "class"]
    functions = [s.name for s in symbols if s.symbol_type == "function"]
    
    assert "UserProfile" in classes
    assert "loadProfile" in functions
    assert "deleteUser" in functions
