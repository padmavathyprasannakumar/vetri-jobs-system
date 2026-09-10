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

import DashboardFooter from "../../components/DashboardFooter/DashboardFooter";

import BrandLogo from "../../components/BrandLogo/BrandLogo";


import "./AdminLayout.css";







const AdminLayout = ()=>{


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



navigate("/student/login");



}


catch(error){


console.log(error);


}



};









const closeSidebar=()=>{


setSidebarOpen(false);


};









return (



<div className="admin-layout">







{/* =====================================
            SIDEBAR
===================================== */}



<aside


className={

sidebarOpen

?

"admin-sidebar open"

:

"admin-sidebar"

}


>






<BrandLogo
wrapperClassName="admin-logo"
circleClassName="admin-logo-circle"
customTagline="Super Admin"
/>









<nav className="admin-menu">







<NavLink


to="/admin/dashboard"


onClick={closeSidebar}


className={({isActive})=>

isActive

?

"admin-nav active"

:

"admin-nav"

}


>


<i className="bi bi-speedometer2"></i>


Dashboard


</NavLink>









<NavLink


to="/admin/users"


onClick={closeSidebar}


className="admin-nav"


>


<i className="bi bi-people"></i>


Users


</NavLink>









<NavLink


to="/admin/roles"


onClick={closeSidebar}


className="admin-nav"


>


<i className="bi bi-shield-lock"></i>


Roles & Permissions


</NavLink>









<NavLink


to="/admin/analytics"


onClick={closeSidebar}


className="admin-nav"


>


<i className="bi bi-bar-chart"></i>


Analytics


</NavLink>









<NavLink


to="/admin/settings"


onClick={closeSidebar}


className="admin-nav"


>


<i className="bi bi-gear"></i>


System Settings


</NavLink>









<NavLink


to="/admin/whatsapp-settings"


onClick={closeSidebar}


className="admin-nav"


>


<i className="bi bi-whatsapp"></i>


WhatsApp Settings


</NavLink>








</nav>






</aside>












{/* =====================================
            MAIN AREA
===================================== */}



<div className="admin-main">







<header className="admin-header">





<button


className="admin-toggle"


onClick={()=>setSidebarOpen(!sidebarOpen)}


>


<i className="bi bi-list"></i>


</button>









<div className="admin-header-right">





<div className="admin-user">


<i className="bi bi-person-circle"></i>



<div>


<strong>


{

user?.username

||

"Super Admin"


}


</strong>


<p>

Administrator

</p>


</div>


</div>








<button


className="admin-logout"


onClick={handleLogout}


>


<i className="bi bi-box-arrow-right"></i>


Logout


</button>







</div>





</header>









<main className="admin-content">


<Outlet/>


</main>


<DashboardFooter/>






</div>










{/* CHATBOT */}



<Chatbot/>






</div>


);


};



export default AdminLayout;