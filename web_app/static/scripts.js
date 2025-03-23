document.getElementById('submitBtn').addEventListener('click', function (event) {
    event.preventDefault();  // Prevent default form submission
    console.log("Submit button clicked!");  
    sendData();
});

function sendData() {
    let phoneNumber = document.getElementById('phone_number').value;
    let message = document.getElementById('message').value;

    console.log("Sending Data:", phoneNumber, message);  

    fetch('/success/', {  // Ensure correct URL
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()  // Include CSRF token
        },
        body: JSON.stringify({
            'phone_number': phoneNumber,
            'message': message
        })
    })
    .then(response => {
        if (response.ok) {
            return response.text();  // ✅ Ensure response is received before redirecting
        }
        throw new Error('Network response was not ok.');
    })
    .then(html => {
        document.open();
        document.write(html);
        document.close();
    })
    .catch(error => {
        console.error("Error:", error);  
    });
}

// Function to get CSRF token
function getCSRFToken() {
    let csrfTokenElement = document.querySelector('[name=csrfmiddlewaretoken]');
    return csrfTokenElement ? csrfTokenElement.value : '';
}
