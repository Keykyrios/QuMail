# html_templates.py

# This file contains professional-grade HTML templates for displaying
# the state of secure messages and the email view pane to the user.

EMPTY_VIEW_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            background-color: #3c3f41; /* Match the QTableWidget background */
            margin: 0;
            padding: 0;
        }}
    </style>
</head>
<body>
    <!-- THIS IS INTENTIONALLY BLANK FOR A CLEAN, DARK, AND CONSISTENT UI -->
</body>
</html>
"""

LOCKED_MESSAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #2E2E3A;
            color: #E0E0E0;
            margin: 0;
            padding: 40px;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            box-sizing: border-box;
        }}
        .container {{
            text-align: center;
            max-width: 500px;
        }}
        .icon {{
            font-size: 60px;
            margin-bottom: 20px;
            color: #70A5F5;
        }}
        h1 {{
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 10px;
            color: #FFFFFF;
        }}
        p {{
            font-size: 16px;
            line-height: 1.6;
            color: #A0A0B0;
        }}
        .spinner {{
            border: 4px solid #4A4A5A;
            border-top: 4px solid #70A5F5;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 30px auto 0 auto;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">&#128274;</div>
        <h1>Quantum-Secure Message</h1>
        <p>This message is encrypted. Please wait while we retrieve the quantum key and decrypt the content.</p>
        <div class="spinner"></div>
    </div>
</body>
</html>
"""

DECRYPTION_FAILED_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #2E2E3A;
            color: #E0E0E0;
            margin: 0;
            padding: 40px;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            box-sizing: border-box;
        }}
        .container {{
            text-align: center;
            max-width: 500px;
            border-left: 4px solid #D9534F;
            padding-left: 20px;
        }}
        .icon {{
            font-size: 60px;
            margin-bottom: 20px;
            color: #D9534F;
        }}
        h1 {{
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 10px;
            color: #FFFFFF;
        }}
        p {{
            font-size: 16px;
            line-height: 1.6;
            color: #A0A0B0;
        }}
        .error-details {{
            margin-top: 20px;
            padding: 15px;
            background-color: #3A3A4A;
            border-radius: 6px;
            font-family: "Courier New", Courier, monospace;
            font-size: 14px;
            color: #E0E0E0;
            text-align: left;
            word-wrap: break-word;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">&#10060;</div>
        <h1>Decryption Failed</h1>
        <p>The message could not be decrypted. This may be due to a missing key, a tampered message, or an internal error.</p>
        <div class="error-details">
            <strong>Error:</strong> {error_message}
        </div>
    </div>
</body>
</html>
"""

