function sendMail(){
    let parms = { 
        name : document.getElementById("name").value,
        email : document.getElementById("email").value,
        subject : document.getElementById("subject").value,
        mesage : document.getElementById("message").value,

    }

    emailjs.send("service_q1zmyp4","template_1q2w3e4", parms).then(function(response) {
        // handle the response here, e.g.:
        console.log("Email sent successfully!", response);
    });
}