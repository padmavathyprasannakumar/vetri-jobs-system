// =====================================================
// PROTECTED ROUTE
// Vetri Jobs Frontend
// JWT + Role Authorization
// =====================================================


import React from "react";


import {

    Navigate,

    Outlet,

    useLocation

} from "react-router-dom";


import {

    useAuth

} from "../context/AuthContext";





const ProtectedRoute = ({

    allowedRoles = []

})=>{


    const {

        user,

        token,

        loading

    } = useAuth();



    const location = useLocation();





    // =====================================================
    // WAIT FOR AUTH RESTORE
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

                    Loading Vetri Jobs...

                    </p>


                </div>


            </div>

        );


    }





    // =====================================================
    // GET TOKEN
    // =====================================================


    const accessToken =

        token ||

        localStorage.getItem(
            "access_token"
        );





    // =====================================================
    // GET USER
    // =====================================================


    let savedUser = user;



    if(!savedUser){


        try{


            const storageUser =

            localStorage.getItem(
                "user"
            );


            if(storageUser){


                savedUser =

                JSON.parse(
                    storageUser
                );


            }


        }

        catch(error){


            console.error(
                "USER STORAGE ERROR",
                error
            );


            localStorage.removeItem(
                "user"
            );


        }


    }







    // =====================================================
    // NOT AUTHENTICATED
    // =====================================================


    if(

        !accessToken ||

        !savedUser

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


    const role =

        String(

            savedUser.role || ""

        )

        .toLowerCase()

        .trim();








    // =====================================================
    // ROLE CHECK
    // =====================================================


    const allowed =


        allowedRoles.map(

            item =>

            String(item)

            .toLowerCase()

            .trim()


        );







    if(


        allowed.length > 0 &&


        !allowed.includes(role)


    ){



        return (

            <Navigate

                to={

                    getDashboardByRole(
                        role
                    )

                }

                replace

            />

        );


    }







    // =====================================================
    // ACCESS GRANTED
    // =====================================================


    return <Outlet/>;



};











// =====================================================
// ROLE DASHBOARD
// =====================================================


const getDashboardByRole=(role)=>{


    switch(role){



        case "student":

            return "/student/dashboard";



        case "company":

            return "/company/dashboard";



        case "placement_admin":

            return "/placement/dashboard";



        case "super_admin":

            return "/";



        default:

            return "/student/login";


    }


};





export default ProtectedRoute;