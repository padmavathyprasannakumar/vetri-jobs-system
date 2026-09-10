import React, {

    useState,

    useEffect,

    useRef

} from "react";


import {

    Outlet,

    NavLink,

    useNavigate

} from "react-router-dom";


import {

    useAuth

} from "../../context/AuthContext";


import Chatbot from "../../components/Chatbot/ChatBot";

import Footer from "../../components/Footer/Footer";

import BrandLogo from "../../components/BrandLogo/BrandLogo";

import api from "../../api/axios";


import "./CompanyLayout.css";








const CompanyLayout = ()=>{


const navigate = useNavigate();


const [sidebarOpen,setSidebarOpen] = useState(false);


const sidebarRef = useRef(null);


useEffect(()=>{

if(sidebarRef.current){

sidebarRef.current.scrollTop = 0;

}

},[]);





const {

    user,

    logout

}=useAuth();








// =====================================
// LOGOUT
// =====================================


const handleLogout = async()=>{


try{


await logout();


navigate("/company/login");


}

catch(error){


console.log(error);


}


};








const closeSidebar=()=>{


setSidebarOpen(false);


};









return (



<div className="company-layout">







{/* =================================
        SIDEBAR
================================= */}



<aside


ref={sidebarRef}


className={

sidebarOpen

?

"company-sidebar open"

:

"company-sidebar"

}


>







<BrandLogo
wrapperClassName="company-sidebar-brand"
circleClassName="company-logo-circle"
customTagline="Recruiter Portal"
/>










<nav className="company-menu">







<NavLink


to="/company/dashboard"


onClick={closeSidebar}


className={({isActive})=>

isActive

?

"company-nav active"

:

"company-nav"

}


>


<i className="bi bi-speedometer2"></i>


Dashboard


</NavLink>








<NavLink


to="/company/profile"


onClick={closeSidebar}


className="company-nav"


>


<i className="bi bi-building"></i>


Company Profile


</NavLink>









<NavLink


to="/company/jobs"


onClick={closeSidebar}


className="company-nav"


>


<i className="bi bi-briefcase"></i>


Manage Jobs


</NavLink>










<NavLink


to="/company/candidates"


onClick={closeSidebar}


className="company-nav"


>


<i className="bi bi-people"></i>


Candidates


</NavLink>








<NavLink


to="/company/interviews"


onClick={closeSidebar}


className="company-nav"


>


<i className="bi bi-calendar-check"></i>


Interviews


</NavLink>









<NavLink


to="/company/analytics"


onClick={closeSidebar}


className="company-nav"


>


<i className="bi bi-bar-chart"></i>


Analytics


</NavLink>


<NavLink

to="/company/ai-assistant"

onClick={closeSidebar}

className="company-nav"

>

<i className="bi bi-robot"></i>

AI Assistant

</NavLink>







</nav>









<div className="company-sidebar-illustration">

<div className="company-sidebar-bot"><i className="bi bi-robot"></i></div>

<h4>Hire Smarter with Vetri AI</h4>

<p>Let AI help you find the right talent faster</p>

<button

onClick={()=>{

const chatBtn = document.querySelector(".chatbot-button");

if(chatBtn) chatBtn.click();

}}

>

Chat with AI

</button>

</div>

</aside>












{/* =================================
        MAIN AREA
================================= */}



<div className="company-main">







<header className="company-header">





<button


className="company-toggle"


onClick={()=>setSidebarOpen(!sidebarOpen)}


>


<i className="bi bi-list"></i>


</button>









<div className="company-header-right">




<div className="company-user">


<i className="bi bi-person-circle"></i>



<div>


<strong>

{

user?.username

||

user?.company_name

||

"Company"

}


</strong>


<p>

Recruiter Account

</p>


</div>


</div>








<button


className="company-logout"


onClick={handleLogout}


>


<i className="bi bi-box-arrow-right"></i>


Logout


</button>







</div>





</header>









<main className="company-content">


<Outlet/>


</main>


<Footer
quickLinks={[
{ label:"Home", to:"/company/dashboard" },
{ label:"Jobs", to:"/company/jobs" },
{ label:"Candidates", to:"/company/candidates" },
{ label:"Profile", to:"/company/profile" },
]}
/>






</div>










{/* CHATBOT */}



<Chatbot/>






</div>


);



};





export default CompanyLayout;