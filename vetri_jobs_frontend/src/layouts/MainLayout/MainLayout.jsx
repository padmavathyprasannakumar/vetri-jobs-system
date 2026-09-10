import React from "react";


import {

    Outlet

} from "react-router-dom";


import Navbar from "../../components/Navbar/Navbar";


import Footer from "../../components/Footer/Footer";


import Chatbot from "../../components/Chatbot/ChatBot";


import "./MainLayout.css";








const MainLayout = ()=>{


return (



<div className="main-layout">











{/* ==========================
        NAVBAR
========================== */}



<header className="main-header">


<Navbar />


</header>










{/* ==========================
        MAIN CONTENT
========================== */}



<main className="main-content">


<Outlet />


</main>










{/* ==========================
        FOOTER
========================== */}



<footer className="main-footer">


<Footer />


</footer>









{/* ==========================
        AI CHATBOT
========================== */}



<Chatbot />






</div>


);


};



export default MainLayout;