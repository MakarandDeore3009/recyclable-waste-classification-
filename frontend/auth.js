const API_URL = window.location.origin;


// ================================
// LOGIN
// ================================

const loginForm = document.getElementById("loginForm");

if (loginForm) {

    loginForm.addEventListener(
        "submit",
        async function (event) {

            event.preventDefault();

            const email =
                document.getElementById(
                    "loginEmail"
                ).value.trim();

            const password =
                document.getElementById(
                    "loginPassword"
                ).value;

            const message =
                document.getElementById(
                    "loginMessage"
                );

            message.textContent =
                "Logging in...";

            try {

                const response = await fetch(
                    `${API_URL}/api/auth/login`,
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body: JSON.stringify({
                            email,
                            password
                        })
                    }
                );

                const data =
                    await response.json();

                if (!response.ok) {

                    message.textContent =
                        data.message ||
                        "Login failed";

                    return;
                }

                // Save authentication
                localStorage.setItem(
                    "sortwise_token",
                    data.token
                );

                localStorage.setItem(
                    "sortwise_user",
                    JSON.stringify(data.user)
                );

                message.textContent =
                    "Login successful!";

                // Go to dashboard
                window.location.href =
                    "index.html";

            } catch (error) {

                console.error(error);

                message.textContent =
                    "Unable to connect to server";
            }
        }
    );
}


// ================================
// SIGNUP
// ================================

const signupForm =
    document.getElementById(
        "signupForm"
    );

if (signupForm) {

    signupForm.addEventListener(
        "submit",
        async function (event) {

            event.preventDefault();

            const username =
                document.getElementById(
                    "signupUsername"
                ).value.trim();

            const email =
                document.getElementById(
                    "signupEmail"
                ).value.trim();

            const password =
                document.getElementById(
                    "signupPassword"
                ).value;

            const confirmPassword =
                document.getElementById(
                    "signupConfirmPassword"
                ).value;

            const message =
                document.getElementById(
                    "signupMessage"
                );

            if (
                password !==
                confirmPassword
            ) {

                message.textContent =
                    "Passwords do not match";

                return;
            }

            message.textContent =
                "Creating account...";

            try {

                const response =
                    await fetch("/api/register", {
    method: "POST",
    headers: {
        "Content-Type": "application/json",
        "Accept": "application/json"
    },
    body: JSON.stringify({
        username: username,
        email: email,
        password: password
    })
});;

                const data =
                    await response.json();

                if (!response.ok) {

                    message.textContent =
                        data.message ||
                        "Registration failed";

                    return;
                }

                message.textContent =
                    "Account created successfully!";

                setTimeout(
                    () => {
                        window.location.href =
                            "login.html";
                    },
                    1000
                );

            } catch (error) {

                console.error(error);

                message.textContent =
                    "Unable to connect to server";
            }
        }
    );
}