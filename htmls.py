not_found_html = """
<html>
  <head>
    <title>404 Not Found</title>
  </head>
  <body style="font-family: Arial; text-align: center; margin-top: 10%;">
    <h1 style="color: #e63946;">404 Not Found</h1>
    <p>Page you are looking for isn't exist yet.</p>
    <img src="https://i.imgflip.com/34124w.jpg?a487392"
         alt="Funny 404"
         style="display: block; margin: 20px auto; width: 20%; height: auto;">
  </body>
</html>

"""

html = ws_page = """
<!DOCTYPE html>
<html>
<head>
    <title>WebSocket Test</title>
</head>
<body>
    <h1>WebSocket Client</h1>

    <button onclick="sendStart()">Start</button>
    <button onclick="sendStop()">Stop</button>

    <ul id="messages"></ul>

    <script>
        var ws = new WebSocket("ws://localhost:8000/ws");

        ws.onmessage = function(event) {
            var messages = document.getElementById('messages');
            var message = document.createElement('li');
            message.textContent = event.data;
            messages.appendChild(message);
        };

        function sendStart() {
            ws.send("start");
        }

        function sendStop() {
            ws.send("stop");
        }
    </script>
</body>
</html>

"""
