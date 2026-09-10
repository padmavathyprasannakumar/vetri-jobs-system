// =====================================================
// AUTH CONTEXT
// Vetri Jobs Frontend
// JWT + Role Based Authentication
// =====================================================


import {

    createContext,

    useContext,

    useEffect,

    useState

} from "react";



import {


    loginUser,

    logoutUser,

    getCurrentUser,

    saveAuthData,

    clearAuthData


} from "../api/authApi";







const AuthContext = createContext(null);









export const AuthProvider = ({children})=>{





const [user,setUser] = useState(null);



const [token,setToken] = useState(

    localStorage.getItem(
        "access_token"
    )

);



const [loading,setLoading] = useState(true);








// =====================================================
// NORMALIZE USER
// =====================================================


const normalizeUser=(data)=>{


    if(!data)

        return null;



    return {


        ...data,


        role:

        String(
            data.role || ""
        )
        .trim()
        .toLowerCase()


    };


};









// =====================================================
// CLEAR AUTH
// =====================================================


const clearAuth=()=>{


    clearAuthData();


    setUser(null);


    setToken(null);


};









// =====================================================
// CHECK LOGIN SESSION
// =====================================================


const checkAuth = async()=>{


    console.log(
        "AUTH CHECK RUNNING"
    );


    try{


        const accessToken =

        localStorage.getItem(
            "access_token"
        );



        const storedUser =

        localStorage.getItem(
            "user"
        );




        // ================================
        // NO TOKEN
        // ================================

        if(!accessToken){


            setUser(null);

            setToken(null);


            return;


        }






        // ================================
        // RESTORE USER FROM STORAGE
        // ================================

        if(storedUser){


            const parsedUser =

            normalizeUser(

                JSON.parse(
                    storedUser
                )

            );



            setUser(parsedUser);


        }






        // ================================
        // SET TOKEN
        // ================================

        setToken(
            accessToken
        );





        /*
        
        IMPORTANT:
        
        Do NOT call getCurrentUser()
        here.
        
        It causes dashboard blinking.
        
        */




    }


    catch(error){


        console.log(

            "AUTH RESTORE ERROR",

            error

        );


        clearAuth();


    }


    finally{


        setLoading(false);


    }


};







// =====================================================
// INITIAL LOAD
// =====================================================


useEffect(()=>{


    checkAuth();


},[]);











// =====================================================
// LOGIN
// =====================================================


const login = async(credentials)=>{


try{


    const response =

    await loginUser(

        credentials

    );




    const data =

    response.data;






    const accessToken =


        data.access

        ||

        data.tokens?.access

        ||

        data.token;






    const refreshToken =


        data.refresh

        ||

        data.tokens?.refresh;







    const loggedUser =

    normalizeUser(

        data.user

    );







    if(!accessToken){


        throw new Error(

            "Access token missing"

        );


    }






    if(!loggedUser){


        throw new Error(

            "User data missing"

        );


    }








    saveAuthData({

        access:

        accessToken,


        refresh:

        refreshToken,


        user:

        loggedUser


    });







    setToken(

        accessToken

    );





    setUser(

        loggedUser

    );







    return {


        success:true,


        user:loggedUser


    };



}

catch(error){



    console.log(

        "LOGIN ERROR",

        error.response?.data

        ||

        error.message

    );



    throw error;


}



};











// =====================================================
// LOGOUT
// =====================================================


const logout = async()=>{


try{


    await logoutUser();



}

catch(error){


    console.log(

        "LOGOUT ERROR",

        error

    );


}


finally{


    clearAuth();


}



};











// =====================================================
// UPDATE USER
// =====================================================


const updateUser=(data)=>{


const updated =

normalizeUser(

    data

);




setUser(

    updated

);




localStorage.setItem(

    "user",

    JSON.stringify(
        updated
    )

);



};











// =====================================================
// ROLE FUNCTIONS
// =====================================================


const getRole=()=>{


return user?.role || null;


};







const hasRole=(role)=>{


return (

    getRole()

    ===

    String(role)

    .toLowerCase()

);



};






const isStudent=()=>hasRole("student");


const isCompany=()=>hasRole("company");


const isPlacementAdmin=()=>hasRole("placement_admin");


const isSuperAdmin=()=>hasRole("super_admin");









// =====================================================
// DASHBOARD ROUTE
// =====================================================


const getDashboardPath=()=>{


switch(getRole()){



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









const value={


    user,


    token,


    loading,


    login,


    logout,


    updateUser,


    hasRole,


    isStudent,


    isCompany,


    isPlacementAdmin,


    isSuperAdmin,


    getDashboardPath,



    isAuthenticated:

    Boolean(

        user && token

    )



};







return(


<AuthContext.Provider

value={value}

>


{children}


</AuthContext.Provider>


);



};









export const useAuth=()=>{


const context =

useContext(

    AuthContext

);




if(!context){


throw new Error(

"useAuth must be inside AuthProvider"

);


}



return context;



};





export default AuthContext;