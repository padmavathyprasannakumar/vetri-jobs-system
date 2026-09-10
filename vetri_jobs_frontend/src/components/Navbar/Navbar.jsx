import React, {
    useState
} from "react";


import {
    Link,
    useNavigate
} from "react-router-dom";


import {
    FaBars,
    FaTimes,
    FaUserCircle,
    FaUserShield
} from "react-icons/fa";

import BrandLogo from "../BrandLogo/BrandLogo";


import {
    useAuth
} from "../../context/AuthContext";


import "./Navbar.css";




const Navbar = ()=>{


const navigate = useNavigate();


const {
    user,
    logout
}=useAuth();



const [menuOpen,setMenuOpen]=useState(false);





const handleLogout=()=>{


logout();


navigate("/");


};







return (


<nav className="navbar">



{/* LOGO */}

<BrandLogo onClick={()=>navigate("/")}/>









{/* MOBILE MENU ICON */}

<div 
className="mobile-menu"
onClick={()=>{
setMenuOpen(!menuOpen)
}}
>


{

menuOpen

?

<FaTimes/>

:

<FaBars/>

}


</div>









<div 
className={
menuOpen
?
"navbar-links active"
:
"navbar-links"
}
>



<Link to="/">

Home

</Link>



{

!user &&

<>


<Link to="/student/register">

For Students

</Link>





<Link to="/company/register">

For Companies

</Link>



<Link to="/placement/login" className="placement-nav-link">

<FaUserShield/>

Placement Admin

</Link>






<div className="register-dropdown">


<button>

Register ▾

</button>



<div className="dropdown-menu">


<Link to="/student/register">

Student Register

</Link>



<Link to="/company/register">

Company Register

</Link>


</div>


</div>



<button

className="navbar-login-btn"

onClick={()=>navigate("/")}

>

Login

</button>



</>


}









{

user && user.role==="student" &&

<>


<Link to="/student/dashboard">

Dashboard

</Link>



<Link to="/student/profile">

Profile

</Link>



<div className="user-box">


<FaUserCircle/>


<span>

{
user.username
}

</span>


</div>



<button
className="logout-btn"
onClick={handleLogout}
>

Logout

</button>



</>

}









{

user && user.role==="company" &&

<>


<Link to="/company/dashboard">

Dashboard

</Link>




<Link to="/company/profile">

Company Profile

</Link>



<div className="user-box">


<FaUserCircle/>


<span>

{
user.username
}

</span>


</div>



<button
className="logout-btn"
onClick={handleLogout}
>

Logout

</button>



</>

}






</div>



</nav>


);


};


export default Navbar;