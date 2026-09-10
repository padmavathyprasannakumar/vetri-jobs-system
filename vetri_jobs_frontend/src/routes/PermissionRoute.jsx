import React from "react";


import {

    Navigate,

    Outlet,

    useLocation

} from "react-router-dom";


import {

    useAuth

} from "../context/AuthContext";






// =====================================================
// PERMISSION ROUTE
// ROLE BASED ACCESS CONTROL
// =====================================================


const PermissionRoute = ({

    children,

    allowedRoles = []

})=>{





const {

    user,

    loading,

    isAuthenticated

}=useAuth();





const location = useLocation();









// =====================================================
// LOADING
// =====================================================


if(loading){



return (

<div className="route-loading">


<div className="loader-box">


<div

className="spinner-border text-primary"

role="status"

>


</div>


<p>

Checking permissions...

</p>



</div>


</div>


);



}









// =====================================================
// GET AUTH USER
// =====================================================


const token =

localStorage.getItem(

"access_token"

);




const storedUser =

JSON.parse(

localStorage.getItem(

"user"

)

);



const currentUser =

user || storedUser;









// =====================================================
// NOT LOGIN
// =====================================================


if(

!token ||

!currentUser ||

!isAuthenticated

){



return (

<Navigate


to="/student/login"


replace


state={{

from:

location.pathname

}}


/>

);



}









// =====================================================
// NORMALIZE ROLE
// =====================================================


const normalizeRole=(role)=>{


return String(role || "")

.trim()

.toLowerCase();



};









const userRole =

normalizeRole(

currentUser.role

);









// =====================================================
// ROLE ALIASES
// =====================================================


const roleAliases={



"admin":

"super_admin",



"superadmin":

"super_admin",



"company_admin":

"company",



"recruiter":

"company",



"employer":

"company",



"placement":

"placement_admin",



"placementadmin":

"placement_admin"


};









const finalUserRole =


roleAliases[userRole]

||

userRole;









const allowed =


allowedRoles.map(

role =>


roleAliases[

normalizeRole(role)

]

||

normalizeRole(role)


);









console.log(

"PERMISSION CHECK",

{

user:

finalUserRole,

allowed

}

);









// =====================================================
// ACCESS CHECK
// =====================================================


if(

allowed.length > 0 &&

!allowed.includes(finalUserRole)

){



return (

<Navigate


to="/unauthorized"


replace


state={{

attemptedPath:

location.pathname,


role:

finalUserRole


}}


/>

);



}









// =====================================================
// SUCCESS
// =====================================================


if(children){


return children;


}



return <Outlet/>;



};









export default PermissionRoute;