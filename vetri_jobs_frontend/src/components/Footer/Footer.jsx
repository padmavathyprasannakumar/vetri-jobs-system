import React from "react";

import { Link } from "react-router-dom";

import {
    FaMapMarkerAlt,
    FaInstagram,
} from "react-icons/fa";

import BrandLogo from "../BrandLogo/BrandLogo";

import "./Footer.css";




// Default Quick Links shown on the public marketing pages.
// Every dashboard layout (student/company/placement/admin) passes
// its own `quickLinks` prop instead, so the SAME footer component
// is reused everywhere with only these 4 links changing.
const DEFAULT_QUICK_LINKS = [
    { label: "Home", to: "/" },
    { label: "Student Portal", to: "/student/login" },
    { label: "Company Portal", to: "/company/login" },
    { label: "Placement Admin", to: "/placement/login" },
];




const Footer = ({ quickLinks = DEFAULT_QUICK_LINKS })=>{

    return(

        <footer className="app-footer">

            <div className="app-footer-top">

                {/* BRAND */}
                <div className="app-footer-section app-footer-brand">

                    <BrandLogo
                    showTagline={false}
                    wrapperClassName="app-footer-logo"
                    circleClassName="app-footer-logo-circle"
                    />

                </div>


                {/* QUICK LINKS */}
                <div className="app-footer-section">

                    <h3>Quick Links</h3>

                    {
                    quickLinks.map((link,index)=>(

                        <Link key={index} to={link.to}>{link.label}</Link>

                    ))
                    }

                </div>


                {/* CONTACT US */}
                <div className="app-footer-section">

                    <h3>Contact Us</h3>

                    <div className="app-footer-address">

                        <FaMapMarkerAlt/>

                        <span>
                            April's Complex, Bus Stand Backside,<br/>
                            Surandai - 627859,<br/>
                            Tenkasi District
                        </span>

                    </div>

                </div>


                {/* FOLLOW US */}
                <div className="app-footer-section">

                    <h3>Follow Us</h3>

                    <div className="app-footer-socials">

                        <a
                        href="https://www.instagram.com"
                        target="_blank"
                        rel="noreferrer"
                        aria-label="Instagram"
                        >
                            <FaInstagram/>
                        </a>

                    </div>

                </div>

            </div>


            <div className="app-footer-bottom">

                &copy; {new Date().getFullYear()} Vetri Jobs. All rights reserved.

            </div>

        </footer>

    );

};


export default Footer;
