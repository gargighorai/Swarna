// flash_messages.js

<script></script>
// Find the flash message container
var flashMessage = document.getElementById('flash-message-container');

// Check if the element exists
if (flashMessage) {
  // Hide the element after 2 seconds (2000 milliseconds)
  setTimeout(function() {
    flashMessage.style.display = 'none';
  }, 2000);
}