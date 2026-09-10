import React from "react";

import ReactDOM from "react-dom/client";


// =====================================================
// APP
// =====================================================

import App from "./App.jsx";


// =====================================================
// CONTEXT PROVIDERS
// =====================================================

import { AuthProvider } from "./context/AuthContext.jsx";

import { ThemeProvider } from "./context/ThemeProvider.jsx";

import { NotificationProvider } from "./context/NotificationProvider.jsx";


// =====================================================
// GLOBAL CSS
// =====================================================

import "bootstrap/dist/css/bootstrap.min.css";

import "bootstrap-icons/font/bootstrap-icons.css";

import "./index.css";

import "./styles/animations.css";

import "./styles/responsive.css";




// =====================================================
// ROOT ELEMENT
// =====================================================

const root = document.getElementById("root");


if(!root){

    throw new Error(
        "Root element not found"
    );

}




// =====================================================
// APPLICATION RENDER
// =====================================================


ReactDOM.createRoot(root).render(

    <ThemeProvider>

        <NotificationProvider>

            <AuthProvider>

                <App />

            </AuthProvider>

        </NotificationProvider>

    </ThemeProvider>

);