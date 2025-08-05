#!/usr/bin/env python3
"""
Comprehensive API Test Script
Tests all endpoints and functionality of the ERP Eleven API
"""

import requests
import json
from datetime import datetime
import uuid

BASE_URL = "http://localhost:8000"

def test_health_check():
    """Test basic health check endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"✅ Health Check: {response.status_code} - {response.json()}")
        return True
    except Exception as e:
        print(f"❌ Health Check Failed: {e}")
        return False

def test_root():
    """Test root endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"✅ Root Endpoint: {response.status_code} - {response.json()}")
        return True
    except Exception as e:
        print(f"❌ Root Endpoint Failed: {e}")
        return False

def test_documentation():
    """Test API documentation endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/docs")
        print(f"✅ API Docs: {response.status_code}")
        return True
    except Exception as e:
        print(f"❌ API Docs Failed: {e}")
        return False

def create_test_user():
    """Create a test user in the database"""
    print("\n🔧 Setting up test user...")
    # This would normally require direct database access
    # For now, we'll use the mock authentication
    return True

def test_authentication():
    """Test authentication endpoints"""
    print("\n🔐 Testing Authentication...")
    
    # Test login with mock credentials
    login_data = {
        "email": "admin@loja.com",
        "senha": "123456"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
        if response.status_code == 200:
            token_data = response.json()
            print(f"✅ Login successful: {response.status_code}")
            return token_data["access_token"]
        else:
            print(f"❌ Login failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Login exception: {e}")
        return None

def test_protected_endpoint(token):
    """Test protected endpoint with authentication"""
    if not token:
        print("❌ No token available for protected endpoint test")
        return False
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        if response.status_code == 200:
            user_data = response.json()
            print(f"✅ Protected endpoint (/api/auth/me): {user_data['nome']}")
            return True
        else:
            print(f"❌ Protected endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Protected endpoint exception: {e}")
        return False

def test_vendors_endpoint(token):
    """Test vendors CRUD operations"""
    print("\n👥 Testing Vendors Endpoints...")
    
    if not token:
        print("❌ No token available for vendors test")
        return False
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test GET vendors
    try:
        response = requests.get(f"{BASE_URL}/api/vendedores/", headers=headers)
        print(f"✅ GET Vendors: {response.status_code} - Found {len(response.json())} vendors")
    except Exception as e:
        print(f"❌ GET Vendors failed: {e}")
    
    # Test POST vendor (this will likely fail due to database constraints)
    vendor_data = {
        "nome": "Test Vendor",
        "taxa_comissao": 15.0,
        "meta_semanal": 1000.0,
        "telefone": "11999999999",
        "ativo": True
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/vendedores/", json=vendor_data, headers=headers)
        if response.status_code == 201:
            print(f"✅ POST Vendor: {response.status_code}")
        else:
            print(f"⚠️ POST Vendor: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ POST Vendor exception: {e}")

def test_sales_endpoint(token):
    """Test sales CRUD operations"""
    print("\n💰 Testing Sales Endpoints...")
    
    if not token:
        print("❌ No token available for sales test")
        return False
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test GET sales
    try:
        response = requests.get(f"{BASE_URL}/api/vendas/", headers=headers)
        print(f"✅ GET Sales: {response.status_code} - Found {len(response.json())} sales")
    except Exception as e:
        print(f"❌ GET Sales failed: {e}")

def test_dashboard_endpoint(token):
    """Test dashboard analytics endpoints"""
    print("\n📊 Testing Dashboard Endpoints...")
    
    if not token:
        print("❌ No token available for dashboard test")
        return False
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test dashboard stats
    try:
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=headers)
        if response.status_code == 200:
            stats = response.json()
            print(f"✅ Dashboard Stats: Total Sales: {stats.get('totalVendas', 0)}")
        else:
            print(f"❌ Dashboard Stats failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Dashboard Stats exception: {e}")

def test_orders_endpoint(token):
    """Test orders CRUD operations"""
    print("\n📦 Testing Orders Endpoints...")
    
    if not token:
        print("❌ No token available for orders test")
        return False
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test GET orders
    try:
        response = requests.get(f"{BASE_URL}/api/pedidos/", headers=headers)
        print(f"✅ GET Orders: {response.status_code} - Found {len(response.json())} orders")
    except Exception as e:
        print(f"❌ GET Orders failed: {e}")

def main():
    """Run all API tests"""
    print("🚀 Starting ERP Eleven API Tests")
    print("=" * 50)
    
    # Basic connectivity tests
    if not test_health_check():
        print("❌ Basic connectivity failed. Is the server running?")
        return
    
    test_root()
    test_documentation()
    
    # Authentication tests
    token = test_authentication()
    test_protected_endpoint(token)
    
    # Endpoint tests
    test_vendors_endpoint(token)
    test_sales_endpoint(token)
    test_dashboard_endpoint(token)
    test_orders_endpoint(token)
    
    print("\n" + "=" * 50)
    print("🏁 API Tests Completed")

if __name__ == "__main__":
    main()