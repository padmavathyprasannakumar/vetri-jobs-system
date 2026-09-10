import React,{

useState,

useEffect

} from "react";


import {

Outlet,

NavLink,

useNavigate

} from "react-router-dom";


import { useNotification } from "../../context/NotificationProvider";



import {

useAuth

} from "../../context/AuthContext";



import Chatbot from "../../components/Chatbot/ChatBot";

import Footer from "../../components/Footer/Footer";

import BrandLogo from "../../components/BrandLogo/BrandLogo";



import {

FaHome,

FaBriefcase,

FaRobot,

FaBookmark,

FaFileAlt,

FaCalendarCheck,

FaBell,

FaUser,

FaFileUpload,

FaSignOutAlt,

FaBars,

FaUserCircle

} from "react-icons/fa";



import "./StudentLayout.css";








const StudentLayout=()=>{



const navigate=useNavigate();



const [sidebarOpen,setSidebarOpen]=useState(false);


const { unreadCount } = useNotification();






const {

user,

logout

}=useAuth();









const handleLogout=async()=>{


await logout();


navigate("/student/login");


};







const closeSidebar=()=>{


setSidebarOpen(false);


};









const menu=[



{

name:"Dashboard",

path:"/student/dashboard",

icon:<FaHome/>

},



{

name:"Jobs",

path:"/student/jobs",

icon:<FaBriefcase/>

},



{

name:"AI Career Assistant",

path:"/student/ai-assistant",

icon:<FaRobot/>

},



{

name:"Saved Jobs",

path:"/student/saved-jobs",

icon:<FaBookmark/>

},



{

name:"Applications",

path:"/student/applications",

icon:<FaFileAlt/>

},



{

name:"Interviews",

path:"/student/interviews",

icon:<FaCalendarCheck/>

},



{

name:"Notifications",

path:"/student/notifications",

icon:<FaBell/>

},



{

name:"Resume",

path:"/student/resume",

icon:<FaFileUpload/>

},



{

name:"Profile",

path:"/student/profile",

icon:<FaUser/>

}



];









return(



<div className="student-layout">







{/* MOBILE OVERLAY */}



{

sidebarOpen &&

<div

className="sidebar-overlay"

onClick={closeSidebar}

/>

}











{/* SIDEBAR */}



<aside

className={

sidebarOpen

?

"student-sidebar open"

:

"student-sidebar"

}

>







<BrandLogo
wrapperClassName="student-brand"
circleClassName="brand-circle"
customTagline="Student Portal"
/>









<nav className="student-navigation">





{

menu.map((item,index)=>(



<NavLink


key={index}


to={item.path}


onClick={closeSidebar}



className={({isActive})=>

isActive

?

"student-link active"

:

"student-link"

}



>


<span>

{item.icon}

</span>


{item.name}


</NavLink>



))

}





</nav>









<div className="sidebar-footer">


<p>

Career Dashboard

</p>


<small>

Find your dream opportunity

</small>


</div>








</aside>













{/* MAIN */}



<div className="student-main">







<header className="student-header">

<div className="student-header-inner">





<button

className="menu-btn"

onClick={()=>setSidebarOpen(!sidebarOpen)}

>

<FaBars/>

</button>









<div className="header-actions">









<button

className="header-bell-btn"

onClick={()=>navigate("/student/notifications")}

title="Notifications"

>

<FaBell/>

{
unreadCount > 0 &&

<span className="header-bell-badge">{unreadCount}</span>
}

</button>


<div className="student-profile-mini">


<FaUserCircle/>




<div>


<h4>


{

user?.username

||

"Student"

}


</h4>



<p>

Student Account

</p>


</div>



</div>









<button


className="logout-btn"


onClick={handleLogout}


>


<FaSignOutAlt/>

Logout


</button>








</div>








</div>

</header>












<main className="student-content">


<Outlet/>


</main>



<Footer
quickLinks={[
{ label:"Home", to:"/student/dashboard" },
{ label:"Jobs", to:"/student/jobs" },
{ label:"Profile", to:"/student/profile" },
{ label:"Services", to:"/student/ai-assistant" },
]}
/>









</div>










{/* AI CHATBOT */}



<Chatbot/>









</div>



);


};



export default StudentLayout;