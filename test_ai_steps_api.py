"""
Quick test to verify AI Steps API endpoints work correctly
Run this after starting the web server on port 8080
"""

import requests
import json

BASE_URL = "http://localhost:8080"

def test_ai_steps_api():
    print("🧪 Testing AI Steps API Endpoints\n")

    # 1. Test GET /api/ai-steps (should be empty initially)
    print("1️⃣ GET /api/ai-steps (initial)")
    response = requests.get(f"{BASE_URL}/api/ai-steps")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 200
    print("   ✅ PASSED\n")

    # 2. Test POST /api/ai-steps (create new AI step)
    print("2️⃣ POST /api/ai-steps (create)")
    test_step = {
        "name": "Test Login",
        "steps": "1. Go to https://example.com\n2. Click login button\n3. Fill email field\n4. Click submit"
    }
    response = requests.post(f"{BASE_URL}/api/ai-steps", json=test_step)
    print(f"   Status: {response.status_code}")
    result = response.json()
    print(f"   Response: {result}")
    assert response.status_code == 200
    assert result.get('success') == True
    filename = result.get('filename')
    print(f"   Created: {filename}")
    print("   ✅ PASSED\n")

    # 3. Test GET /api/ai-steps (should have 1 item now)
    print("3️⃣ GET /api/ai-steps (after create)")
    response = requests.get(f"{BASE_URL}/api/ai-steps")
    print(f"   Status: {response.status_code}")
    steps = response.json()
    print(f"   Count: {len(steps)}")
    assert response.status_code == 200
    assert len(steps) == 1
    assert steps[0]['name'] == "Test Login"
    print("   ✅ PASSED\n")

    # 4. Test GET /api/ai-steps/<filename> (get specific)
    print(f"4️⃣ GET /api/ai-steps/{filename}")
    response = requests.get(f"{BASE_URL}/api/ai-steps/{filename}")
    print(f"   Status: {response.status_code}")
    step_data = response.json()
    print(f"   Name: {step_data.get('name')}")
    assert response.status_code == 200
    assert step_data.get('name') == "Test Login"
    print("   ✅ PASSED\n")

    # 5. Test PUT /api/ai-steps/<filename> (update)
    print(f"5️⃣ PUT /api/ai-steps/{filename} (update)")
    updated_step = {
        "name": "Test Login Updated",
        "steps": "1. Go to https://example.com\n2. Click login\n3. Enter credentials\n4. Submit\n5. Verify success",
        "created": step_data.get('created')
    }
    response = requests.put(f"{BASE_URL}/api/ai-steps/{filename}", json=updated_step)
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 200
    print("   ✅ PASSED\n")

    # 6. Verify update worked
    print(f"6️⃣ GET /api/ai-steps/{filename} (verify update)")
    response = requests.get(f"{BASE_URL}/api/ai-steps/{filename}")
    step_data = response.json()
    print(f"   Name: {step_data.get('name')}")
    assert step_data.get('name') == "Test Login Updated"
    print("   ✅ PASSED\n")

    # 7. Test DELETE /api/ai-steps/<filename>
    print(f"7️⃣ DELETE /api/ai-steps/{filename}")
    response = requests.delete(f"{BASE_URL}/api/ai-steps/{filename}")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 200
    print("   ✅ PASSED\n")

    # 8. Verify deletion
    print("8️⃣ GET /api/ai-steps (verify deletion)")
    response = requests.get(f"{BASE_URL}/api/ai-steps")
    steps = response.json()
    print(f"   Count: {len(steps)}")
    assert len(steps) == 0
    print("   ✅ PASSED\n")

    print("🎉 ALL TESTS PASSED!")

if __name__ == "__main__":
    try:
        test_ai_steps_api()
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Cannot connect to server at http://localhost:8080")
        print("   Please start the web server first: python web_ui.py")
    except AssertionError as e:
        print(f"❌ TEST FAILED: {e}")
    except Exception as e:
        print(f"❌ ERROR: {e}")
