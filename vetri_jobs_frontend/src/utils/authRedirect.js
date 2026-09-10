export const redirectByRole = (navigate, user) => {


    const role =
        user?.role
        ?.trim()
        ?.toLowerCase();



    console.log(
        "REDIRECT ROLE:",
        role
    );



    switch(role){


        case "student":

            navigate(
                "/student/dashboard",
                {
                    replace:true
                }
            );

            break;



        case "company":

            navigate(
                "/company/dashboard",
                {
                    replace:true
                }
            );

            break;



        case "placement_admin":

            navigate(
                "/placement/dashboard",
                {
                    replace:true
                }
            );

            break;



        case "super_admin":

            navigate(
                "/",
                {
                    replace:true
                }
            );

            break;



        default:

            console.log(
                "Unknown role:",
                role
            );


            navigate(
                "/login"
            );

    }


};