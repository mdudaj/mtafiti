# Promoted Behavioral Patterns

## Page Patterns

### Admin

- route: `/accounts/profile/`
- layout_type: `form`
- components: `form, header, main, section, table, ul`
- interactions: `form-submit, link-navigation`
- internal_navigation: `/accounts/password_change/`

### CRUD sample

- route: `/atlas/city/`
- layout_type: `workflow_form`
- components: `aside, form, header, main, nav, section, table, ul`
- interactions: `form-submit, form-submit, form-submit, link-navigation`
- internal_navigation: `/accounts/profile/, /api/, /atlas/, /atlas/city/, /atlas/city/2049/detail/, /atlas/city/2093/detail/, /atlas/city/2122/detail/, /atlas/city/2218/detail/, /atlas/city/2226/detail/, /atlas/city/2356/detail/, /atlas/city/2357/detail/, /atlas/city/2552/detail/, /atlas/city/2566/detail/, /atlas/city/2649/detail/, /atlas/city/2653/detail/, /atlas/city/2692/detail/, /atlas/city/2707/detail/, /atlas/city/2841/detail/, /atlas/city/2890/detail/, /atlas/city/2949/detail/, /atlas/city/3591/detail/, /atlas/city/3639/detail/, /atlas/city/3718/detail/, /atlas/city/3773/detail/, /atlas/city/3796/detail/, /atlas/city/3938/detail/, /atlas/city/3953/detail/, /atlas/city/3991/detail/, /atlas/city/4058/detail/, /atlas/continent/, /atlas/country/, /atlas/forms/, /atlas/ocean/, /atlas/sea/, /dashboard/, /intro/, /patterns/, /review/, /workflow/`

### CRUD sample

- route: `/atlas/city/`
- layout_type: `workflow_form`
- components: `aside, form, header, main, nav, section, table, ul`
- interactions: `form-submit, form-submit, form-submit, link-navigation`
- internal_navigation: `/accounts/profile/, /api/, /atlas/, /atlas/city/, /atlas/city/2049/detail/, /atlas/city/2093/detail/, /atlas/city/2122/detail/, /atlas/city/2218/detail/, /atlas/city/2226/detail/, /atlas/city/2356/detail/, /atlas/city/2357/detail/, /atlas/city/2552/detail/, /atlas/city/2566/detail/, /atlas/city/2649/detail/, /atlas/city/2653/detail/, /atlas/city/2692/detail/, /atlas/city/2707/detail/, /atlas/city/2841/detail/, /atlas/city/2890/detail/, /atlas/city/2949/detail/, /atlas/city/3591/detail/, /atlas/city/3639/detail/, /atlas/city/3718/detail/, /atlas/city/3773/detail/, /atlas/city/3796/detail/, /atlas/city/3938/detail/, /atlas/city/3953/detail/, /atlas/city/3991/detail/, /atlas/city/4058/detail/, /atlas/continent/, /atlas/country/, /atlas/forms/, /atlas/ocean/, /atlas/sea/, /dashboard/, /intro/, /patterns/, /review/, /workflow/`

### CRUD sample

- route: `/atlas/continent/`
- layout_type: `workflow_form`
- components: `aside, form, header, main, nav, section, table, ul`
- interactions: `form-submit, form-submit, form-submit, link-navigation`
- internal_navigation: `/accounts/profile/, /api/, /atlas/, /atlas/city/, /atlas/continent/, /atlas/continent/Africa/change/, /atlas/continent/Antarctica/change/, /atlas/continent/Asia/change/, /atlas/continent/Australia/change/, /atlas/continent/Europe/change/, /atlas/continent/North%20America/change/, /atlas/continent/South%20America/change/, /atlas/country/, /atlas/forms/, /atlas/ocean/, /atlas/sea/, /dashboard/, /intro/, /patterns/, /review/, /workflow/`

### CRUD sample

- route: `/atlas/continent/Europe/change/`
- layout_type: `workflow_form`
- components: `aside, form, header, main, nav, section, ul`
- interactions: `form-submit, form-submit, link-navigation`
- internal_navigation: `/accounts/profile/, /api/, /atlas/, /atlas/city/, /atlas/continent/, /atlas/country/, /atlas/forms/, /atlas/ocean/, /atlas/sea/, /dashboard/, /intro/, /patterns/, /review/, /workflow/`

### CRUD sample

- route: `/atlas/country/`
- layout_type: `workflow_form`
- components: `aside, form, header, main, nav, section, table, ul`
- interactions: `form-submit, form-submit, form-submit, link-navigation`
- internal_navigation: `/accounts/profile/, /api/, /atlas/, /atlas/city/, /atlas/continent/, /atlas/country/, /atlas/country/10/change/, /atlas/country/11/change/, /atlas/country/118/change/, /atlas/country/121/change/, /atlas/country/122/change/, /atlas/country/160/change/, /atlas/country/161/change/, /atlas/country/168/change/, /atlas/country/169/change/, /atlas/country/176/change/, /atlas/country/177/change/, /atlas/country/192/change/, /atlas/country/193/change/, /atlas/country/206/change/, /atlas/country/36/change/, /atlas/country/52/change/, /atlas/country/60/change/, /atlas/country/68/change/, /atlas/country/71/change/, /atlas/country/72/change/, /atlas/country/8/change/, /atlas/country/84/change/, /atlas/country/85/change/, /atlas/country/9/change/, /atlas/country/94/change/, /atlas/forms/, /atlas/ocean/, /atlas/sea/, /dashboard/, /intro/, /patterns/, /review/, /workflow/`

### CRUD sample

- route: `/atlas/country/121/delete/`
- layout_type: `workflow_form`
- components: `aside, form, header, main, nav, section, ul`
- interactions: `form-submit, form-submit, link-navigation`
- internal_navigation: `/accounts/profile/, /api/, /atlas/, /atlas/city/, /atlas/city/2058/detail/, /atlas/city/2059/detail/, /atlas/city/2060/detail/, /atlas/city/2061/detail/, /atlas/city/2062/detail/, /atlas/city/2063/detail/, /atlas/city/2064/detail/, /atlas/city/2065/detail/, /atlas/city/2066/detail/, /atlas/city/2067/detail/, /atlas/continent/, /atlas/country/, /atlas/country/121/change/, /atlas/forms/, /atlas/ocean/, /atlas/sea/, /dashboard/, /intro/, /patterns/, /review/, /workflow/`

### Forms

- route: `/atlas/forms/bank/`
- layout_type: `workflow_form`
- components: `aside, form, header, main, nav, section, ul`
- interactions: `form-submit, form-submit, link-navigation`
- internal_navigation: `/accounts/profile/, /api/, /atlas/, /atlas/forms/bank/, /atlas/forms/checkout/, /atlas/forms/contact/, /atlas/forms/hospital/, /atlas/forms/login/, /atlas/forms/profile/, /atlas/forms/registration/, /atlas/forms/signup/, /atlas/forms/wizard/, /dashboard/, /intro/, /patterns/, /review/, /workflow/`

### Forms

- route: `/atlas/forms/hospital/`
- layout_type: `workflow_form`
- components: `aside, form, header, main, nav, section, ul`
- interactions: `form-submit, form-submit, link-navigation`
- internal_navigation: `/accounts/profile/, /api/, /atlas/, /atlas/forms/bank/, /atlas/forms/checkout/, /atlas/forms/contact/, /atlas/forms/hospital/, /atlas/forms/login/, /atlas/forms/profile/, /atlas/forms/registration/, /atlas/forms/signup/, /atlas/forms/wizard/, /dashboard/, /intro/, /patterns/, /review/, /workflow/`

### Forms

- route: `/atlas/forms/registration/`
- layout_type: `workflow_form`
- components: `aside, form, header, main, nav, section, ul`
- interactions: `form-submit, form-submit, link-navigation`
- internal_navigation: `/accounts/profile/, /api/, /atlas/, /atlas/forms/bank/, /atlas/forms/checkout/, /atlas/forms/contact/, /atlas/forms/hospital/, /atlas/forms/login/, /atlas/forms/profile/, /atlas/forms/registration/, /atlas/forms/signup/, /atlas/forms/wizard/, /dashboard/, /intro/, /patterns/, /review/, /workflow/`

### Forms

- route: `/atlas/forms/signup/`
- layout_type: `workflow_form`
- components: `aside, form, header, main, nav, section, ul`
- interactions: `form-submit, form-submit, link-navigation`
- internal_navigation: `/accounts/profile/, /api/, /atlas/, /atlas/forms/bank/, /atlas/forms/checkout/, /atlas/forms/contact/, /atlas/forms/hospital/, /atlas/forms/login/, /atlas/forms/profile/, /atlas/forms/registration/, /atlas/forms/signup/, /atlas/forms/wizard/, /dashboard/, /intro/, /patterns/, /review/, /workflow/`

### CRUD sample

- route: `/atlas/ocean/`
- layout_type: `workflow_form`
- components: `aside, form, header, main, nav, section, table, ul`
- interactions: `form-submit, link-navigation`
- internal_navigation: `/accounts/profile/, /api/, /atlas/, /atlas/city/, /atlas/continent/, /atlas/country/, /atlas/forms/, /atlas/ocean/, /atlas/ocean/Arctic/detail/, /atlas/ocean/Atlantic/detail/, /atlas/ocean/Indian/detail/, /atlas/ocean/Pacific/detail/, /atlas/ocean/Southern/detail/, /atlas/sea/, /dashboard/, /intro/, /patterns/, /review/, /workflow/`

### CRUD sample

- route: `/atlas/sea/`
- layout_type: `workflow_form`
- components: `aside, form, header, main, nav, section, table, ul`
- interactions: `form-submit, form-submit, form-submit, link-navigation`
- internal_navigation: `/accounts/profile/, /api/, /atlas/, /atlas/city/, /atlas/continent/, /atlas/country/, /atlas/forms/, /atlas/ocean/, /atlas/sea/, /atlas/sea/1/change/, /atlas/sea/11/change/, /atlas/sea/12/change/, /atlas/sea/13/change/, /atlas/sea/14/change/, /atlas/sea/15/change/, /atlas/sea/2/change/, /atlas/sea/21/change/, /atlas/sea/22/change/, /atlas/sea/23/change/, /atlas/sea/24/change/, /atlas/sea/25/change/, /atlas/sea/26/change/, /atlas/sea/27/change/, /atlas/sea/28/change/, /atlas/sea/29/change/, /atlas/sea/3/change/, /atlas/sea/30/change/, /atlas/sea/31/change/, /atlas/sea/32/change/, /atlas/sea/33/change/, /atlas/sea/34/change/, /atlas/sea/35/change/, /atlas/sea/4/change/, /atlas/sea/7/change/, /dashboard/, /intro/, /patterns/, /review/, /workflow/`

### Demo dashboards

- route: `/dashboard/django_stats/`
- layout_type: `workflow_form`
- components: `aside, form, header, main, nav, section, ul`
- interactions: `form-submit, link-navigation`
- internal_navigation: `/accounts/profile/, /api/, /atlas/, /dashboard/, /dashboard/django_stats/, /dashboard/oilngas/, /dashboard/stocks/, /intro/, /intro/vf_stats/, /patterns/, /review/, /workflow/`

### Demo dashboards

- route: `/dashboard/oilngas/`
- layout_type: `workflow_form`
- components: `aside, form, header, main, nav, section, ul`
- interactions: `form-submit, link-navigation`
- internal_navigation: `/accounts/profile/, /api/, /atlas/, /dashboard/, /dashboard/django_stats/, /dashboard/oilngas/, /dashboard/stocks/, /intro/, /intro/vf_stats/, /patterns/, /review/, /workflow/`

### Demo dashboards

- route: `/dashboard/oilngas/`
- layout_type: `workflow_form`
- components: `aside, form, header, main, nav, section, ul`
- interactions: `form-submit, link-navigation`
- internal_navigation: `/accounts/profile/, /api/, /atlas/, /dashboard/, /dashboard/django_stats/, /dashboard/oilngas/, /dashboard/stocks/, /intro/, /intro/vf_stats/, /patterns/, /review/, /workflow/`

### Demo dashboards

- route: `/dashboard/stocks/`
- layout_type: `workflow_form`
- components: `aside, form, header, main, nav, section, ul`
- interactions: `form-submit, link-navigation`
- internal_navigation: `/accounts/profile/, /api/, /atlas/, /dashboard/, /dashboard/django_stats/, /dashboard/oilngas/, /dashboard/stocks/, /intro/, /intro/vf_stats/, /patterns/, /review/, /workflow/`

### Applications

- route: `/intro/`
- layout_type: `workflow_form`
- components: `aside, form, header, main, nav, section, ul`
- interactions: `form-submit, link-navigation`
- internal_navigation: `/accounts/profile/, /admin/review/review/, /api/, /atlas/, /atlas/city/, /atlas/continent/Europe/change/, /atlas/country/121/delete/, /atlas/forms/comment/, /atlas/forms/hospital/, /atlas/forms/registration/, /atlas/forms/signup/, /dashboard/, /intro/, /intro/vf_stats/, /patterns/, /review/, /review/api/swagger/, /review/review/, /workflow/`

### Applications

- route: `/intro/`
- layout_type: `workflow_form`
- components: `aside, form, header, main, nav, section, ul`
- interactions: `form-submit, link-navigation`
- internal_navigation: `/accounts/profile/, /admin/review/review/, /api/, /atlas/, /atlas/city/, /atlas/continent/Europe/change/, /atlas/country/121/delete/, /atlas/forms/comment/, /atlas/forms/hospital/, /atlas/forms/registration/, /atlas/forms/signup/, /dashboard/, /intro/, /intro/vf_stats/, /patterns/, /review/, /review/api/swagger/, /review/review/, /workflow/`

### Applications

- route: `/intro/vf_stats/`
- layout_type: `workflow_form`
- components: `aside, form, header, main, nav, section, ul`
- interactions: `form-submit, link-navigation`
- internal_navigation: `/accounts/profile/, /api/, /atlas/, /dashboard/, /intro/, /patterns/, /review/, /workflow/`

### WF Patterns

- route: `/patterns/sequence/`
- layout_type: `workflow_form`
- components: `aside, form, header, main, nav, section, ul`
- interactions: `form-submit, link-navigation`
- internal_navigation: `/accounts/profile/, /api/, /atlas/, /dashboard/, /intro/, /patterns/, /patterns/cancelingpartialjoin/, /patterns/defferedchoice/, /patterns/exclusivechoice/, /patterns/loop/, /patterns/multimerge/, /patterns/multipleinstances/, /patterns/parallelsplit/, /patterns/partialjoin/, /patterns/resource_allocation/, /patterns/sequence/, /patterns/sequence/7079/input_user_details/238528/assign/, /patterns/sequence/7083/input_user_details/238552/assign/, /patterns/sequence/7092/input_user_details/238598/execute/, /patterns/sequence/7094/, /patterns/sequence/7115/input_user_details/238731/assign/, /patterns/sequence/7126/input_user_details/238974/assign/, /patterns/sequence/7127/input_user_details/238976/execute/, /patterns/sequence/7135/input_user_details/239007/assign/, /patterns/sequence/7143/, /patterns/sequence/7145/input_user_details/239057/assign/, /patterns/sequence/7157/input_user_details/239119/assign/, /patterns/sequence/7168/, /patterns/sequence/7177/, /patterns/sequence/7180/, /patterns/sequence/7185/, /patterns/sequence/7187/, /patterns/sequence/7189/, /patterns/sequence/7194/, /patterns/sequence/7196/input_user_details/239363/assign/, /patterns/sequence/7199/input_user_details/239372/assign/, /patterns/sequence/7203/input_user_details/239390/execute/, /patterns/sequence/7215/input_user_details/239490/assign/, /patterns/sequence/7216/input_user_details/239492/assign/, /patterns/sequence/7217/input_user_details/239496/assign/, /patterns/sequence/7220/input_user_details/239547/assign/, /patterns/sequence/7225/, /patterns/sequence/7226/, /patterns/sequence/7228/, /patterns/sequence/7229/input_user_details/239582/assign/, /patterns/sequence/7230/input_user_details/239584/assign/, /patterns/sequence/7231/input_user_details/239588/execute/, /patterns/sequence/7233/, /patterns/sequence/7234/, /patterns/sequence/7235/, /patterns/sequence/7236/, /patterns/sequence/7237/, /patterns/sequence/7251/, /patterns/sequence/7252/, /patterns/sequence/7253/input_user_details/239742/assign/, /patterns/sequence/7254/, /patterns/sequence/7255/, /patterns/sequence/7258/input_user_details/239759/assign/, /patterns/sequence/7259/input_user_details/239761/execute/, /patterns/sequence/7260/, /patterns/sequence/7264/, /patterns/sequence/7267/, /patterns/sequence/7271/, /patterns/sequence/7282/input_user_details/239890/execute/, /patterns/sequence/7284/input_user_details/239895/assign/, /patterns/sequence/7285/input_user_details/239897/assign/, /patterns/sequence/flows/, /patterns/sequence/start/, /patterns/sequence/tasks/, /review/, /workflow/`

### FSM Flow Demo

- route: `/review/api/swagger/`
- layout_type: `workflow_form`
- components: `aside, form, header, main, nav, section, ul`
- interactions: `form-submit, link-navigation`
- internal_navigation: `/accounts/profile/, /admin/review/review/, /api/, /atlas/, /dashboard/, /intro/, /patterns/, /review/, /review/api/swagger/, /review/review/, /workflow/`

### FSM Flow Demo

- route: `/review/review/`
- layout_type: `workflow_form`
- components: `aside, form, header, main, nav, section, table, ul`
- interactions: `form-submit, form-submit, link-navigation`
- internal_navigation: `/accounts/profile/, /admin/review/review/, /api/, /atlas/, /dashboard/, /intro/, /patterns/, /review/, /review/api/swagger/, /review/review/, /review/review/751/detail/, /review/review/770/detail/, /review/review/778/detail/, /review/review/801/detail/, /review/review/822/detail/, /review/review/826/detail/, /review/review/828/detail/, /review/review/842/detail/, /review/review/845/detail/, /review/review/849/detail/, /review/review/851/detail/, /workflow/`

### FSM Flow Demo

- route: `/review/review/`
- layout_type: `workflow_form`
- components: `aside, form, header, main, nav, section, table, ul`
- interactions: `form-submit, form-submit, link-navigation`
- internal_navigation: `/accounts/profile/, /admin/review/review/, /api/, /atlas/, /dashboard/, /intro/, /patterns/, /review/, /review/api/swagger/, /review/review/, /review/review/751/detail/, /review/review/770/detail/, /review/review/778/detail/, /review/review/801/detail/, /review/review/822/detail/, /review/review/826/detail/, /review/review/828/detail/, /review/review/842/detail/, /review/review/845/detail/, /review/review/849/detail/, /review/review/851/detail/, /workflow/`

### Workflow

- route: `/workflow/inbox/`
- layout_type: `workflow_form`
- components: `aside, form, header, main, nav, section, table, ul`
- interactions: `form-submit, form-submit, form-submit, link-navigation`
- internal_navigation: `/accounts/profile/, /api/, /atlas/, /dashboard/, /intro/, /patterns/, /review/, /workflow/, /workflow/archive/, /workflow/flows/, /workflow/flows/dynamicsplit/start/, /workflow/flows/helloworld/start/, /workflow/flows/shipment/start/, /workflow/inbox/, /workflow/queue/`
