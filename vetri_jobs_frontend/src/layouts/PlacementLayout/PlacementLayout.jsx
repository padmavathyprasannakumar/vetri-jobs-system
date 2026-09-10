import React, {

    useState

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


import "./PlacementLayout.css";







const PlacementLayout = ()=>{


const navigate = useNavigate();


const [sidebarOpen,setSidebarOpen] = useState(false);





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


navigate("/placement/login");


}

catch(error){


console.log(error);


}


};









const closeSidebar=()=>{


setSidebarOpen(false);


};









return (



<div className="placement-layout">







{/* =====================================
            SIDEBAR
===================================== */}



<aside


className={

sidebarOpen

?

"placement-sidebar open"

:

"placement-sidebar"

}


>








<BrandLogo
wrapperClassName="placement-logo"
circleClassName="placement-logo-circle"
customTagline="Placement Portal"
/>









<nav className="placement-menu">







<NavLink


to="/placement/dashboard"


onClick={closeSidebar}


className={({isActive})=>

isActive

?

"placement-nav active"

:

"placement-nav"

}


>


<i className="bi bi-speedometer2"></i>


Dashboard


</NavLink>









<NavLink


to="/placement/students"


onClick={closeSidebar}


className="placement-nav"


>


<i className="bi bi-mortarboard"></i>


Students


</NavLink>








<NavLink


to="/placement/companies"


onClick={closeSidebar}


className="placement-nav"


>


<i className="bi bi-building"></i>


Companies


</NavLink>









<NavLink


to="/placement/drives"


onClick={closeSidebar}


className="placement-nav"


>


<i className="bi bi-calendar-event"></i>


Placement Drives


</NavLink>


<NavLink


to="/placement/job-listings"


onClick={closeSidebar}


className="placement-nav"


>


<i className="bi bi-briefcase"></i>


Job Listings


</NavLink>


<NavLink


to="/placement/resumes"


onClick={closeSidebar}


className="placement-nav"


>


<i className="bi bi-file-earmark-person"></i>


Manage Resumes


</NavLink>


<NavLink


to="/placement/notifications"


onClick={closeSidebar}


className="placement-nav"


>


<i className="bi bi-bell"></i>


Send Notifications


</NavLink>




<NavLink


to="/placement/candidate-pipeline"


onClick={closeSidebar}


className="placement-nav"


>


<i className="bi bi-people"></i>


Candidate Pipeline


</NavLink>


<NavLink


to="/placement/ai-chatbot"


onClick={closeSidebar}


className="placement-nav"


>


<i className="bi bi-robot"></i>


AI Chatbot


</NavLink>









<NavLink


to="/placement/reports"


onClick={closeSidebar}


className="placement-nav"


>


<i className="bi bi-file-earmark-bar-graph"></i>


Reports


</NavLink>









</nav>








</aside>












{/* =====================================
            MAIN CONTENT
===================================== */}



<div className="placement-main">







<header className="placement-header">





<button


className="placement-toggle"


onClick={()=>setSidebarOpen(!sidebarOpen)}


>


<i className="bi bi-list"></i>


</button>









<div className="placement-header-right">






<div className="placement-user">


<i className="bi bi-person-circle"></i>



<div>


<strong>

{

user?.username

||

"Placement Admin"

}


</strong>


<p>

Placement Officer

</p>


</div>


</div>








<button


className="placement-logout"


onClick={handleLogout}


>


<i className="bi bi-box-arrow-right"></i>


Logout


</button>






</div>





</header>









<main className="placement-content">


<Outlet/>


</main>


<Footer
quickLinks={[
{ label:"Home", to:"/placement/dashboard" },
{ label:"Students", to:"/placement/students" },
{ label:"Companies", to:"/placement/companies" },
{ label:"Placement Drives", to:"/placement/drives" },
]}
/>








</div>









{/* AI CHATBOT */}



<Chatbot/>






</div>


);


};



export default PlacementLayout;