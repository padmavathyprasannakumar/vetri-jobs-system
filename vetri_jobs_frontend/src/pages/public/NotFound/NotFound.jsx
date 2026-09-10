import React from "react";

import { Link } from "react-router-dom";

import "./NotFound.css";




const NotFound = ()=>{

    return(

        <div className="not-found-page">

            <div className="not-found-illustration">

                <svg viewBox="0 0 240 180" fill="none">

                    <circle cx="120" cy="90" r="80" fill="#eef2ff"/>

                    <rect x="60" y="70" width="120" height="80" rx="10"
                    fill="white" stroke="#4338ca" strokeWidth="4"/>

                    <line x1="60" y1="92" x2="180" y2="92" stroke="#4338ca" strokeWidth="4"/>

                    <circle cx="76" cy="81" r="3" fill="#4338ca"/>
                    <circle cx="88" cy="81" r="3" fill="#4338ca"/>
                    <circle cx="100" cy="81" r="3" fill="#4338ca"/>

                    <path d="M92 125l14 14M106 125l-14 14" stroke="#4338ca" strokeWidth="5" strokeLinecap="round"/>
                    <circle cx="99" cy="132" r="16" fill="none" stroke="#4338ca" strokeWidth="4" opacity=".35"/>

                    <path d="M130 118h34M130 128h24M130 138h30" stroke="#c7d2fe" strokeWidth="4" strokeLinecap="round"/>

                </svg>

            </div>

            <h1>404</h1>

            <h2>Page Not Found</h2>

            <p>The page you're looking for doesn't exist or may have been moved.</p>

            <Link to="/" className="not-found-home-btn">
                Back to Home
            </Link>

        </div>

    );

};


export default NotFound;
