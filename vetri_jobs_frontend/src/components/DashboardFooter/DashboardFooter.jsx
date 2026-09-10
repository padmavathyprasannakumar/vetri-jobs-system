import React from "react";

import "./DashboardFooter.css";


const DashboardFooter = ()=>{

    return(

        <footer className="dashboard-footer">

            <span>

                &copy; {new Date().getFullYear()} Vetri Jobs. All rights reserved.

            </span>

            <span className="dashboard-footer-tagline">

                Empowering Careers, Building Futures.

            </span>

        </footer>

    );

};


export default DashboardFooter;
