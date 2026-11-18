# Inventaire technique — menus contextuels YEM

Base du 18 novembre 2026 : `0d9ee8ecb374c6263ad9c363d2bb2d6bc661a05a` (PR #200 fusionnée).

Recensement automatisé des fichiers et déclarations de routes, complété par la revue des parcours prioritaires dans [l’audit](context-menu-audit-20261118.md). Ce recensement ne constitue pas une revue humaine de toutes les lignes ni une preuve de sécurité exhaustive.

85 fichiers JSX hors tests ; 155 fichiers Python hors migrations/tests ; 302 déclarations de routes, inclusions comprises ; 57 fichiers de tests frontend ; 71 fichiers de tests backend.

## Composants et écrans

| Fichier | Intégration directe |
|---|---|
| [AcademicPanel.jsx](../frontend/AcademicPanel.jsx) | Pas de menu propre ; composants partagés possibles |
| [AdminPasswordReset.jsx](../frontend/AdminPasswordReset.jsx) | Pas de menu propre ; composants partagés possibles |
| [AdmissionCashDesk.jsx](../frontend/AdmissionCashDesk.jsx) | Pas de menu propre ; composants partagés possibles |
| [AdmissionFinance.jsx](../frontend/AdmissionFinance.jsx) | Pas de menu propre ; composants partagés possibles |
| [AdmissionRoutesPanel.jsx](../frontend/AdmissionRoutesPanel.jsx) | Pas de menu propre ; composants partagés possibles |
| [AdmissionsPanel.jsx](../frontend/AdmissionsPanel.jsx) | Menu explicite |
| [AnnualWorkspace.jsx](../frontend/AnnualWorkspace.jsx) | Pas de menu propre ; composants partagés possibles |
| [App.jsx](../frontend/App.jsx) | Pas de menu propre ; composants partagés possibles |
| [AssessmentPanel.jsx](../frontend/AssessmentPanel.jsx) | Menu explicite |
| [AttendancePanel.jsx](../frontend/AttendancePanel.jsx) | Menu explicite |
| [AuthPanel.jsx](../frontend/AuthPanel.jsx) | Pas de menu propre ; composants partagés possibles |
| [CashClosingPanel.jsx](../frontend/CashClosingPanel.jsx) | Pas de menu propre ; composants partagés possibles |
| [ClassWorkspace.jsx](../frontend/ClassWorkspace.jsx) | Menu explicite |
| [CommercialAccess.jsx](../frontend/CommercialAccess.jsx) | Pas de menu propre ; composants partagés possibles |
| [CommercialAdjustments.jsx](../frontend/CommercialAdjustments.jsx) | Pas de menu propre ; composants partagés possibles |
| [CommercialDashboard.jsx](../frontend/CommercialDashboard.jsx) | Menu explicite |
| [CommercialReminders.jsx](../frontend/CommercialReminders.jsx) | Menu explicite |
| [CommercialSimulator.jsx](../frontend/CommercialSimulator.jsx) | Pas de menu propre ; composants partagés possibles |
| [ContextMenu.jsx](../frontend/ContextMenu.jsx) | Menu explicite |
| [CouncilPanel.jsx](../frontend/CouncilPanel.jsx) | Pas de menu propre ; composants partagés possibles |
| [CourseProgress.jsx](../frontend/CourseProgress.jsx) | Pas de menu propre ; composants partagés possibles |
| [CurriculumPanel.jsx](../frontend/CurriculumPanel.jsx) | Menu explicite |
| [CycleScopeManager.jsx](../frontend/CycleScopeManager.jsx) | Pas de menu propre ; composants partagés possibles |
| [CycleWorkspace.jsx](../frontend/CycleWorkspace.jsx) | Pas de menu propre ; composants partagés possibles |
| [DelegationManager.jsx](../frontend/DelegationManager.jsx) | Pas de menu propre ; composants partagés possibles |
| [DemoExperience.jsx](../frontend/DemoExperience.jsx) | Pas de menu propre ; composants partagés possibles |
| [DemoPaymentSetup.jsx](../frontend/DemoPaymentSetup.jsx) | Pas de menu propre ; composants partagés possibles |
| [EnrollmentScreens.jsx](../frontend/EnrollmentScreens.jsx) | Menu explicite |
| [FinancePanel.jsx](../frontend/FinancePanel.jsx) | Menu explicite |
| [FinancialDocuments.jsx](../frontend/FinancialDocuments.jsx) | Menu explicite |
| [LegacyApp.jsx](../frontend/LegacyApp.jsx) | Pas de menu propre ; composants partagés possibles |
| [LiveScreens.jsx](../frontend/LiveScreens.jsx) | Menu explicite |
| [main.jsx](../frontend/main.jsx) | Pas de menu propre ; composants partagés possibles |
| [MonthlyTariffSetup.jsx](../frontend/MonthlyTariffSetup.jsx) | Pas de menu propre ; composants partagés possibles |
| [OperatingPanel.jsx](../frontend/OperatingPanel.jsx) | Menu explicite |
| [OrganisationPanel.jsx](../frontend/OrganisationPanel.jsx) | Pas de menu propre ; composants partagés possibles |
| [OwnerDashboard.jsx](../frontend/OwnerDashboard.jsx) | Pas de menu propre ; composants partagés possibles |
| [OwnerSubscription.jsx](../frontend/OwnerSubscription.jsx) | Pas de menu propre ; composants partagés possibles |
| [ParentDiscovery.jsx](../frontend/ParentDiscovery.jsx) | Pas de menu propre ; composants partagés possibles |
| [ParentExistingSchool.jsx](../frontend/ParentExistingSchool.jsx) | Pas de menu propre ; composants partagés possibles |
| [ParentPortal.jsx](../frontend/ParentPortal.jsx) | Pas de menu propre ; composants partagés possibles |
| [ParentSchoolForms.jsx](../frontend/ParentSchoolForms.jsx) | Pas de menu propre ; composants partagés possibles |
| [PayrollPanel.jsx](../frontend/PayrollPanel.jsx) | Menu explicite |
| [PedagogicalCalendar.jsx](../frontend/PedagogicalCalendar.jsx) | Menu explicite |
| [PlatformConsole.jsx](../frontend/PlatformConsole.jsx) | Menu explicite |
| [PlatformSubscriptions.jsx](../frontend/PlatformSubscriptions.jsx) | Pas de menu propre ; composants partagés possibles |
| [PlatformTariffPolicy.jsx](../frontend/PlatformTariffPolicy.jsx) | Pas de menu propre ; composants partagés possibles |
| [PreschoolFollowup.jsx](../frontend/PreschoolFollowup.jsx) | Pas de menu propre ; composants partagés possibles |
| [PrimaryCriteria.jsx](../frontend/PrimaryCriteria.jsx) | Pas de menu propre ; composants partagés possibles |
| [PrimaryMastery.jsx](../frontend/PrimaryMastery.jsx) | Pas de menu propre ; composants partagés possibles |
| [PWAInstall.jsx](../frontend/PWAInstall.jsx) | Pas de menu propre ; composants partagés possibles |
| [RealDemoExperience.jsx](../frontend/RealDemoExperience.jsx) | Pas de menu propre ; composants partagés possibles |
| [ReportPanel.jsx](../frontend/ReportPanel.jsx) | Menu explicite |
| [RoleManager.jsx](../frontend/RoleManager.jsx) | Pas de menu propre ; composants partagés possibles |
| [SchoolBrandingSettings.jsx](../frontend/SchoolBrandingSettings.jsx) | Pas de menu propre ; composants partagés possibles |
| [SchoolConductPanel.jsx](../frontend/SchoolConductPanel.jsx) | Pas de menu propre ; composants partagés possibles |
| [SchoolDashboard.jsx](../frontend/SchoolDashboard.jsx) | Politique abonnement |
| [SchoolDashboardHeader.jsx](../frontend/SchoolDashboardHeader.jsx) | Pas de menu propre ; composants partagés possibles |
| [SchoolDirectories.jsx](../frontend/SchoolDirectories.jsx) | Menu explicite |
| [SchoolNotificationCenter.jsx](../frontend/SchoolNotificationCenter.jsx) | Menu explicite |
| [SchoolPanel.jsx](../frontend/SchoolPanel.jsx) | Pas de menu propre ; composants partagés possibles |
| [SchoolPaymentSetup.jsx](../frontend/SchoolPaymentSetup.jsx) | Pas de menu propre ; composants partagés possibles |
| [SchoolSettings.jsx](../frontend/SchoolSettings.jsx) | Pas de menu propre ; composants partagés possibles |
| [SchoolWorkspace.jsx](../frontend/SchoolWorkspace.jsx) | Pas de menu propre ; composants partagés possibles |
| [SecondaryMastery.jsx](../frontend/SecondaryMastery.jsx) | Pas de menu propre ; composants partagés possibles |
| [SingPayControl.jsx](../frontend/SingPayControl.jsx) | Pas de menu propre ; composants partagés possibles |
| [SingPayPayment.jsx](../frontend/SingPayPayment.jsx) | Pas de menu propre ; composants partagés possibles |
| [StaffOnboarding.jsx](../frontend/StaffOnboarding.jsx) | Pas de menu propre ; composants partagés possibles |
| [StaffPanel.jsx](../frontend/StaffPanel.jsx) | Pas de menu propre ; composants partagés possibles |
| [StaffProfessionalDossier.jsx](../frontend/StaffProfessionalDossier.jsx) | Pas de menu propre ; composants partagés possibles |
| [StudentNumberingSettings.jsx](../frontend/StudentNumberingSettings.jsx) | Pas de menu propre ; composants partagés possibles |
| [StudentPanel.jsx](../frontend/StudentPanel.jsx) | Pas de menu propre ; composants partagés possibles |
| [SubscriptionDocuments.jsx](../frontend/SubscriptionDocuments.jsx) | Menu explicite |
| [TeacherHome.jsx](../frontend/TeacherHome.jsx) | Pas de menu propre ; composants partagés possibles |
| [TeacherMobileAttendance.jsx](../frontend/TeacherMobileAttendance.jsx) | Menu explicite |
| [TeacherMobileGrades.jsx](../frontend/TeacherMobileGrades.jsx) | Menu explicite |
| [TeacherMobileWorkspace.jsx](../frontend/TeacherMobileWorkspace.jsx) | Pas de menu propre ; composants partagés possibles |
| [TeacherProfile.jsx](../frontend/TeacherProfile.jsx) | Pas de menu propre ; composants partagés possibles |
| [TeachingDiary.jsx](../frontend/TeachingDiary.jsx) | Menu explicite |
| [TimetablePanel.jsx](../frontend/TimetablePanel.jsx) | Menu explicite |
| [yem-ui.jsx](../frontend/yem-ui.jsx) | Menu explicite |
| [YemDesktop.jsx](../frontend/YemDesktop.jsx) | Pas de menu propre ; composants partagés possibles |
| [YemFamilles.jsx](../frontend/YemFamilles.jsx) | Pas de menu propre ; composants partagés possibles |
| [YemFamillesFidele.jsx](../frontend/YemFamillesFidele.jsx) | Pas de menu propre ; composants partagés possibles |
| [YemMobile.jsx](../frontend/YemMobile.jsx) | Pas de menu propre ; composants partagés possibles |

## Routes

| Déclaration | Route relative | Vue |
|---|---|---|
| [backend/config/urls.py:6](../backend/config/urls.py#L6) | `api/v1/auth/` | `include('accounts.urls')` |
| [backend/config/urls.py:7](../backend/config/urls.py#L7) | `api/v1/` | `include('institutions.urls')` |
| [backend/config/urls.py:8](../backend/config/urls.py#L8) | `manifest.webmanifest` | `pwa_asset` |
| [backend/config/urls.py:9](../backend/config/urls.py#L9) | `service-worker.js` | `pwa_asset` |
| [backend/config/urls.py:10](../backend/config/urls.py#L10) | `offline.html` | `pwa_asset` |
| [backend/config/urls.py:11](../backend/config/urls.py#L11) | `icons/icon-192.png` | `pwa_asset` |
| [backend/config/urls.py:12](../backend/config/urls.py#L12) | `icons/icon-512.png` | `pwa_asset` |
| [backend/config/urls.py:13](../backend/config/urls.py#L13) | `parents-app/` | `views.index` |
| [backend/config/urls.py:14](../backend/config/urls.py#L14) | `/` | `views.index` |
| [backend/config/urls.py:15](../backend/config/urls.py#L15) | `healthz` | `views.health` |
| [backend/config/urls.py:16](../backend/config/urls.py#L16) | `readyz` | `views.ready` |
| [backend/config/urls.py:17](../backend/config/urls.py#L17) | `api/v1/presets` | `views.preset_list` |
| [backend/config/urls.py:18](../backend/config/urls.py#L18) | `api/v1/policies/validate` | `views.validate` |
| [backend/config/urls.py:19](../backend/config/urls.py#L19) | `api/v1/evaluate` | `views.simulate` |
| [backend/accounts/urls.py:5](../backend/accounts/urls.py#L5) | `csrf` | `views.csrf` |
| [backend/accounts/urls.py:6](../backend/accounts/urls.py#L6) | `parents/registration-status` | `parent_signup_views.registration_status` |
| [backend/accounts/urls.py:7](../backend/accounts/urls.py#L7) | `parents/resend-verification` | `parent_signup_views.resend_verification` |
| [backend/accounts/urls.py:8](../backend/accounts/urls.py#L8) | `parents/register` | `parent_signup_views.register` |
| [backend/accounts/urls.py:9](../backend/accounts/urls.py#L9) | `parents/verify` | `parent_signup_views.verify` |
| [backend/accounts/urls.py:10](../backend/accounts/urls.py#L10) | `me` | `views.me` |
| [backend/accounts/urls.py:11](../backend/accounts/urls.py#L11) | `login` | `views.sign_in` |
| [backend/accounts/urls.py:12](../backend/accounts/urls.py#L12) | `logout` | `views.sign_out` |
| [backend/accounts/urls.py:13](../backend/accounts/urls.py#L13) | `password/change` | `views.change_password` |
| [backend/accounts/urls.py:14](../backend/accounts/urls.py#L14) | `password/reset/request` | `views.password_reset_request` |
| [backend/accounts/urls.py:15](../backend/accounts/urls.py#L15) | `password/reset/confirm` | `views.password_reset_confirm` |
| [backend/accounts/urls.py:16](../backend/accounts/urls.py#L16) | `password/admin-reset` | `password_admin_views.admin_password_reset` |
| [backend/accounts/urls.py:17](../backend/accounts/urls.py#L17) | `password/admin-parent-reset` | `password_admin_views.admin_parent_password_reset` |
| [backend/accounts/urls.py:18](../backend/accounts/urls.py#L18) | `mfa/begin` | `views.mfa_begin` |
| [backend/accounts/urls.py:19](../backend/accounts/urls.py#L19) | `mfa/confirm` | `views.mfa_confirm` |
| [backend/accounts/urls.py:20](../backend/accounts/urls.py#L20) | `mfa/disable` | `views.mfa_disable` |
| [backend/accounts/urls.py:21](../backend/accounts/urls.py#L21) | `audit` | `views.platform_audit` |
| [backend/institutions/urls.py:23](../backend/institutions/urls.py#L23) | `schools/<uuid:school_id>/branding` | `school_branding_views.school_branding` |
| [backend/institutions/urls.py:24](../backend/institutions/urls.py#L24) | `schools/<uuid:school_id>/branding/<str:kind>` | `school_branding_views.school_brand_image` |
| [backend/institutions/urls.py:25](../backend/institutions/urls.py#L25) | `schools/<uuid:school_id>/owner/overview` | `owner_overview_views.owner_overview` |
| [backend/institutions/urls.py:26](../backend/institutions/urls.py#L26) | `schools/<uuid:school_id>/student-numbering` | `student_numbering_views.numbering` |
| [backend/institutions/urls.py:27](../backend/institutions/urls.py#L27) | `schools/<uuid:school_id>/imports/students/profiles` | `import_views.profiles` |
| [backend/institutions/urls.py:28](../backend/institutions/urls.py#L28) | `schools/<uuid:school_id>/imports/students/export` | `import_views.export_students` |
| [backend/institutions/urls.py:29](../backend/institutions/urls.py#L29) | `schools/<uuid:school_id>/imports/students/inspect` | `import_views.inspect` |
| [backend/institutions/urls.py:30](../backend/institutions/urls.py#L30) | `schools/<uuid:school_id>/imports/students/preview` | `import_views.preview` |
| [backend/institutions/urls.py:31](../backend/institutions/urls.py#L31) | `schools/<uuid:school_id>/imports/students/commit` | `import_views.commit` |
| [backend/institutions/urls.py:32](../backend/institutions/urls.py#L32) | `parents/singpay/webhook` | `singpay_views.webhook` |
| [backend/institutions/urls.py:33](../backend/institutions/urls.py#L33) | `parents/singpay/<str:kind>/<uuid:object_id>/quote` | `singpay_views.quote` |
| [backend/institutions/urls.py:34](../backend/institutions/urls.py#L34) | `parents/singpay/<str:kind>/<uuid:object_id>/pay` | `singpay_views.pay` |
| [backend/institutions/urls.py:35](../backend/institutions/urls.py#L35) | `parents/singpay/payments/<uuid:intent_id>/refresh` | `singpay_views.refresh` |
| [backend/institutions/urls.py:36](../backend/institutions/urls.py#L36) | `parents/singpay/payments/<uuid:intent_id>/receipt` | `singpay_views.receipt` |
| [backend/institutions/urls.py:37](../backend/institutions/urls.py#L37) | `schools/<uuid:school_id>/singpay/merchant` | `singpay_views.merchant_config` |
| [backend/institutions/urls.py:38](../backend/institutions/urls.py#L38) | `schools/<uuid:school_id>/singpay/merchant/verify` | `singpay_views.merchant_verify` |
| [backend/institutions/urls.py:39](../backend/institutions/urls.py#L39) | `schools/<uuid:school_id>/singpay/reconciliation` | `singpay_views.staff_reconciliation` |
| [backend/institutions/urls.py:40](../backend/institutions/urls.py#L40) | `schools/<uuid:school_id>/singpay/payments/<uuid:intent_id>/settlement` | `singpay_views.settlement` |
| [backend/institutions/urls.py:41](../backend/institutions/urls.py#L41) | `schools/<uuid:school_id>/functions` | `delegation_views.functions` |
| [backend/institutions/urls.py:42](../backend/institutions/urls.py#L42) | `schools/<uuid:school_id>/delegations` | `delegation_views.delegations` |
| [backend/institutions/urls.py:43](../backend/institutions/urls.py#L43) | `schools/<uuid:school_id>/delegations/<uuid:delegation_id>` | `delegation_views.delegations` |
| [backend/institutions/urls.py:44](../backend/institutions/urls.py#L44) | `platform/dashboard` | `platform_admin_views.platform_dashboard` |
| [backend/institutions/urls.py:45](../backend/institutions/urls.py#L45) | `platform/subscription-reminders` | `subscription_reminders.commercial_reminders` |
| [backend/institutions/urls.py:46](../backend/institutions/urls.py#L46) | `platform/commercial-dashboard` | `subscription_dashboard.financial_dashboard` |
| [backend/institutions/urls.py:47](../backend/institutions/urls.py#L47) | `platform/schools/<uuid:school_id>/commercial-access` | `subscription_access.commercial_access` |
| [backend/institutions/urls.py:48](../backend/institutions/urls.py#L48) | `schools/<uuid:school_id>/owner/commercial-access` | `subscription_access.commercial_access` |
| [backend/institutions/urls.py:49](../backend/institutions/urls.py#L49) | `schools/<uuid:school_id>/owner/subscription-reminders` | `subscription_reminders.commercial_reminders` |
| [backend/institutions/urls.py:50](../backend/institutions/urls.py#L50) | `platform/subscription-pricing` | `subscription_views.pricing_policy` |
| [backend/institutions/urls.py:51](../backend/institutions/urls.py#L51) | `platform/schools/<uuid:school_id>/subscription-simulation` | `subscription_views.subscription_simulation` |
| [backend/institutions/urls.py:52](../backend/institutions/urls.py#L52) | `schools/<uuid:school_id>/owner/subscription-simulation` | `subscription_views.subscription_simulation` |
| [backend/institutions/urls.py:53](../backend/institutions/urls.py#L53) | `platform/schools/<uuid:school_id>/subscriptions` | `subscription_views.subscriptions` |
| [backend/institutions/urls.py:54](../backend/institutions/urls.py#L54) | `schools/<uuid:school_id>/owner/subscriptions` | `subscription_views.owner_subscriptions` |
| [backend/institutions/urls.py:55](../backend/institutions/urls.py#L55) | `platform/schools/<uuid:school_id>/subscriptions/<int:subscription_id>/invoice` | `subscription_views.commercial_document` |
| [backend/institutions/urls.py:56](../backend/institutions/urls.py#L56) | `platform/schools/<uuid:school_id>/subscriptions/<int:subscription_id>/payments/<int:payment_id>/receipt` | `subscription_views.commercial_document` |
| [backend/institutions/urls.py:57](../backend/institutions/urls.py#L57) | `schools/<uuid:school_id>/owner/subscriptions/<int:subscription_id>/invoice` | `subscription_views.commercial_document` |
| [backend/institutions/urls.py:58](../backend/institutions/urls.py#L58) | `platform/schools/<uuid:school_id>/subscriptions/<int:subscription_id>/amendments/<int:amendment_id>/document` | `subscription_views.commercial_document` |
| [backend/institutions/urls.py:59](../backend/institutions/urls.py#L59) | `schools/<uuid:school_id>/owner/subscriptions/<int:subscription_id>/amendments/<int:amendment_id>/document` | `subscription_views.commercial_document` |
| [backend/institutions/urls.py:60](../backend/institutions/urls.py#L60) | `schools/<uuid:school_id>/owner/subscriptions/<int:subscription_id>/payments/<int:payment_id>/receipt` | `subscription_views.commercial_document` |
| [backend/institutions/urls.py:61](../backend/institutions/urls.py#L61) | `platform/organizations` | `platform_admin_views.platform_organizations` |
| [backend/institutions/urls.py:62](../backend/institutions/urls.py#L62) | `platform/audit` | `platform_admin_views.platform_audit` |
| [backend/institutions/urls.py:63](../backend/institutions/urls.py#L63) | `platform/schools` | `platform_views.platform_schools` |
| [backend/institutions/urls.py:64](../backend/institutions/urls.py#L64) | `platform/schools/<uuid:school_id>/detail` | `platform_admin_views.platform_school_detail` |
| [backend/institutions/urls.py:65](../backend/institutions/urls.py#L65) | `platform/schools/<uuid:school_id>/action` | `platform_admin_views.platform_school_action` |
| [backend/institutions/urls.py:66](../backend/institutions/urls.py#L66) | `platform/schools/<uuid:school_id>/members` | `platform_admin_views.platform_school_members` |
| [backend/institutions/urls.py:67](../backend/institutions/urls.py#L67) | `platform/schools/<uuid:school_id>/members/<uuid:member_id>/action` | `platform_admin_views.platform_member_action` |
| [backend/institutions/urls.py:68](../backend/institutions/urls.py#L68) | `platform/schools/<uuid:school_id>/users` | `platform_views.platform_add_user` |
| [backend/institutions/urls.py:69](../backend/institutions/urls.py#L69) | `platform/schools/<uuid:school_id>/admin-access` | `platform_views.platform_assume_school_administration` |
| [backend/institutions/urls.py:70](../backend/institutions/urls.py#L70) | `parents/paycentral/webhook` | `parent_payment_views.paycentral_webhook` |
| [backend/institutions/urls.py:71](../backend/institutions/urls.py#L71) | `parents/notifications` | `parent_payment_views.family_notifications` |
| [backend/institutions/urls.py:72](../backend/institutions/urls.py#L72) | `parents/push-device` | `parent_push_views.push_device` |
| [backend/institutions/urls.py:73](../backend/institutions/urls.py#L73) | `parents/notification-messages` | `family_notification_views.parent_message` |
| [backend/institutions/urls.py:74](../backend/institutions/urls.py#L74) | `parents/notification-messages/<uuid:notice_id>` | `family_notification_views.parent_notice_detail` |
| [backend/institutions/urls.py:75](../backend/institutions/urls.py#L75) | `parents/applications/<uuid:application_id>/payments` | `parent_payment_views.parent_payment_status` |
| [backend/institutions/urls.py:76](../backend/institutions/urls.py#L76) | `parents/applications/<uuid:application_id>/pay` | `parent_payment_views.parent_pay` |
| [backend/institutions/urls.py:77](../backend/institutions/urls.py#L77) | `parents/applications/<uuid:application_id>/payment-refresh` | `parent_payment_views.parent_payment_refresh` |
| [backend/institutions/urls.py:78](../backend/institutions/urls.py#L78) | `schools/<uuid:school_id>/admission-cash` | `admission_cash_views.cashier_queue` |
| [backend/institutions/urls.py:79](../backend/institutions/urls.py#L79) | `schools/<uuid:school_id>/admission-cash/<uuid:application_id>/confirm` | `admission_cash_views.confirm_cash` |
| [backend/institutions/urls.py:80](../backend/institutions/urls.py#L80) | `schools/<uuid:school_id>/admission-cash/<uuid:application_id>/void` | `admission_cash_views.void_cash` |
| [backend/institutions/urls.py:81](../backend/institutions/urls.py#L81) | `schools/<uuid:school_id>/admission-cash/<uuid:application_id>/receipt` | `admission_cash_views.staff_receipt` |
| [backend/institutions/urls.py:82](../backend/institutions/urls.py#L82) | `parents/applications/<uuid:application_id>/cash-receipt` | `admission_cash_views.parent_receipt` |
| [backend/institutions/urls.py:83](../backend/institutions/urls.py#L83) | `schools/<uuid:school_id>/demo-admission-payments` | `demo_payment_views.school_demo_configuration` |
| [backend/institutions/urls.py:84](../backend/institutions/urls.py#L84) | `schools/<uuid:school_id>/admission-gateway` | `parent_payment_views.school_gateway` |
| [backend/institutions/urls.py:85](../backend/institutions/urls.py#L85) | `schools/<uuid:school_id>/admission-fees` | `parent_payment_views.school_admission_fees` |
| [backend/institutions/urls.py:86](../backend/institutions/urls.py#L86) | `schools/<uuid:school_id>/admission-payments` | `parent_payment_views.staff_admission_payments` |
| [backend/institutions/urls.py:87](../backend/institutions/urls.py#L87) | `parents/existing-schools` | `parent_existing_views.school_directory` |
| [backend/institutions/urls.py:88](../backend/institutions/urls.py#L88) | `parents/existing-requests` | `parent_existing_views.family_requests` |
| [backend/institutions/urls.py:89](../backend/institutions/urls.py#L89) | `parents/existing-requests/<uuid:request_id>` | `parent_existing_views.family_request_detail` |
| [backend/institutions/urls.py:90](../backend/institutions/urls.py#L90) | `schools/<uuid:school_id>/finance/enrollments/<uuid:enrollment_id>/reminder` | `family_notification_views.send_payment_reminder` |
| [backend/institutions/urls.py:91](../backend/institutions/urls.py#L91) | `schools/<uuid:school_id>/notification-inbox` | `family_notification_views.school_inbox` |
| [backend/institutions/urls.py:92](../backend/institutions/urls.py#L92) | `schools/<uuid:school_id>/notification-inbox/<uuid:notice_id>` | `family_notification_views.school_notice_detail` |
| [backend/institutions/urls.py:93](../backend/institutions/urls.py#L93) | `schools/<uuid:school_id>/notification-inbox/requests/<uuid:request_id>/candidates` | `family_notification_views.request_candidates` |
| [backend/institutions/urls.py:94](../backend/institutions/urls.py#L94) | `schools/<uuid:school_id>/parent-existing-requests` | `parent_existing_views.school_requests` |
| [backend/institutions/urls.py:95](../backend/institutions/urls.py#L95) | `schools/<uuid:school_id>/parent-existing-requests/<uuid:request_id>` | `parent_existing_views.school_request_detail` |
| [backend/institutions/urls.py:96](../backend/institutions/urls.py#L96) | `parents/catalog` | `parent_admission_views.directory` |
| [backend/institutions/urls.py:97](../backend/institutions/urls.py#L97) | `parents/admission-form` | `parent_dossier_views.school_form` |
| [backend/institutions/urls.py:98](../backend/institutions/urls.py#L98) | `parents/family-children/<uuid:child_id>` | `parent_dossier_views.family_profile` |
| [backend/institutions/urls.py:99](../backend/institutions/urls.py#L99) | `parents/family-children/<uuid:child_id>/photo` | `parent_dossier_views.family_photo` |
| [backend/institutions/urls.py:100](../backend/institutions/urls.py#L100) | `parents/applications/<uuid:request_id>/documents` | `parent_dossier_views.parent_documents` |
| [backend/institutions/urls.py:101](../backend/institutions/urls.py#L101) | `parents/applications/<uuid:request_id>/documents/<str:code>` | `parent_dossier_views.upload_parent_document` |
| [backend/institutions/urls.py:102](../backend/institutions/urls.py#L102) | `parents/applications/<uuid:request_id>/documents/<str:code>/file` | `parent_dossier_views.parent_document_file` |
| [backend/institutions/urls.py:103](../backend/institutions/urls.py#L103) | `schools/<uuid:school_id>/admissions/<uuid:application_id>/documents/<str:code>/file` | `parent_dossier_views.school_document_file` |
| [backend/institutions/urls.py:104](../backend/institutions/urls.py#L104) | `parents/family-children` | `parent_admission_views.family_children` |
| [backend/institutions/urls.py:105](../backend/institutions/urls.py#L105) | `parents/applications` | `parent_admission_views.family_applications` |
| [backend/institutions/urls.py:106](../backend/institutions/urls.py#L106) | `schools/<uuid:school_id>/parent-listing` | `parent_admission_views.listing_settings` |
| [backend/institutions/urls.py:107](../backend/institutions/urls.py#L107) | `parents/children` | `parent_views.children` |
| [backend/institutions/urls.py:108](../backend/institutions/urls.py#L108) | `parents/children/<uuid:student_id>/enrollments` | `parent_views.child_enrollments` |
| [backend/institutions/urls.py:109](../backend/institutions/urls.py#L109) | `parents/children/<uuid:student_id>/grades` | `parent_views.child_grades` |
| [backend/institutions/urls.py:110](../backend/institutions/urls.py#L110) | `parents/children/<uuid:student_id>/diary` | `teaching_diary_views.child_diary` |
| [backend/institutions/urls.py:111](../backend/institutions/urls.py#L111) | `parents/children/<uuid:student_id>/diary/resources/<uuid:resource_id>` | `diary_resource_views.child_resource` |
| [backend/institutions/urls.py:112](../backend/institutions/urls.py#L112) | `parents/children/<uuid:student_id>/liaison` | `preschool_followup_views.child_liaison` |
| [backend/institutions/urls.py:113](../backend/institutions/urls.py#L113) | `parents/children/<uuid:student_id>/reports` | `parent_views.child_reports` |
| [backend/institutions/urls.py:114](../backend/institutions/urls.py#L114) | `parents/children/<uuid:student_id>/reports/<uuid:report_id>` | `parent_views.child_report_detail` |
| [backend/institutions/urls.py:115](../backend/institutions/urls.py#L115) | `parents/children/<uuid:student_id>/reports/<uuid:report_id>/pdf` | `parent_views.child_report_pdf` |
| [backend/institutions/urls.py:116](../backend/institutions/urls.py#L116) | `parents/children/<uuid:student_id>/attendance` | `parent_views.child_attendance` |
| [backend/institutions/urls.py:117](../backend/institutions/urls.py#L117) | `parents/children/<uuid:student_id>/finance` | `parent_views.child_finance` |
| [backend/institutions/urls.py:118](../backend/institutions/urls.py#L118) | `parents/children/<uuid:student_id>/finance/documents` | `finance_parent_documents.list_documents` |
| [backend/institutions/urls.py:119](../backend/institutions/urls.py#L119) | `parents/children/<uuid:student_id>/finance/documents/<str:kind>/<uuid:document_id>/pdf` | `finance_parent_documents.document_pdf` |
| [backend/institutions/urls.py:120](../backend/institutions/urls.py#L120) | `parents/children/<uuid:student_id>/finance/enrollments/<uuid:enrollment_id>/notice` | `finance_extra_documents.parent_notice` |
| [backend/institutions/urls.py:121](../backend/institutions/urls.py#L121) | `parents/children/<uuid:student_id>/finance/payments/<uuid:payment_id>/cancellation-pdf` | `finance_extra_documents.parent_void_document` |
| [backend/institutions/urls.py:122](../backend/institutions/urls.py#L122) | `parents/children/<uuid:student_id>/timetable` | `parent_views.child_timetable` |
| [backend/institutions/urls.py:123](../backend/institutions/urls.py#L123) | `schools/<uuid:school_id>/parent-links` | `parent_views.links` |
| [backend/institutions/urls.py:124](../backend/institutions/urls.py#L124) | `schools/<uuid:school_id>/parent-links/<uuid:link_id>` | `parent_views.link_detail` |
| [backend/institutions/urls.py:125](../backend/institutions/urls.py#L125) | `schools/<uuid:school_id>/admissions/finance-policy` | `admission_finance_views.finance_rule` |
| [backend/institutions/urls.py:126](../backend/institutions/urls.py#L126) | `schools/<uuid:school_id>/admissions/<uuid:application_id>/scholarship` | `admission_finance_views.scholarship` |
| [backend/institutions/urls.py:127](../backend/institutions/urls.py#L127) | `schools/<uuid:school_id>/admissions/policy` | `admission_route_views.policy` |
| [backend/institutions/urls.py:128](../backend/institutions/urls.py#L128) | `schools/<uuid:school_id>/admissions` | `admission_views.applications` |
| [backend/institutions/urls.py:129](../backend/institutions/urls.py#L129) | `schools/<uuid:school_id>/admissions/<uuid:application_id>/documents` | `admission_route_views.evidence` |
| [backend/institutions/urls.py:130](../backend/institutions/urls.py#L130) | `schools/<uuid:school_id>/admissions/<uuid:application_id>/documents/<uuid:document_id>/review` | `admission_route_views.review_evidence` |
| [backend/institutions/urls.py:131](../backend/institutions/urls.py#L131) | `schools/<uuid:school_id>/admissions/<uuid:application_id>/eligibility` | `admission_route_views.eligibility` |
| [backend/institutions/urls.py:132](../backend/institutions/urls.py#L132) | `schools/<uuid:school_id>/admissions/capacity/<uuid:classroom_id>` | `admission_views.capacity` |
| [backend/institutions/urls.py:133](../backend/institutions/urls.py#L133) | `schools/<uuid:school_id>/admissions/<uuid:application_id>` | `admission_views.application_detail` |
| [backend/institutions/urls.py:134](../backend/institutions/urls.py#L134) | `schools/<uuid:school_id>/admissions/<uuid:application_id>/decide` | `admission_views.decide` |
| [backend/institutions/urls.py:135](../backend/institutions/urls.py#L135) | `schools/<uuid:school_id>/admissions/<uuid:application_id>/convert` | `admission_views.convert` |
| [backend/institutions/urls.py:136](../backend/institutions/urls.py#L136) | `schools/<uuid:school_id>/admissions/<uuid:application_id>/history` | `admission_views.history` |
| [backend/institutions/urls.py:137](../backend/institutions/urls.py#L137) | `schools/<uuid:school_id>/timetable/rooms` | `timetable_views.rooms` |
| [backend/institutions/urls.py:138](../backend/institutions/urls.py#L138) | `schools/<uuid:school_id>/timetable/rooms/<uuid:room_id>` | `timetable_views.room_detail` |
| [backend/institutions/urls.py:139](../backend/institutions/urls.py#L139) | `schools/<uuid:school_id>/timetable/slots` | `timetable_views.slots` |
| [backend/institutions/urls.py:140](../backend/institutions/urls.py#L140) | `schools/<uuid:school_id>/timetable/slots/<uuid:slot_id>` | `timetable_views.slot_detail` |
| [backend/institutions/urls.py:141](../backend/institutions/urls.py#L141) | `schools/<uuid:school_id>/timetable/entries` | `timetable_views.entries` |
| [backend/institutions/urls.py:142](../backend/institutions/urls.py#L142) | `schools/<uuid:school_id>/timetable/entries/<uuid:entry_id>` | `timetable_views.entry_detail` |
| [backend/institutions/urls.py:143](../backend/institutions/urls.py#L143) | `schools/<uuid:school_id>/attendance/options` | `attendance_views.options` |
| [backend/institutions/urls.py:144](../backend/institutions/urls.py#L144) | `schools/<uuid:school_id>/attendance/sessions` | `attendance_views.sessions` |
| [backend/institutions/urls.py:145](../backend/institutions/urls.py#L145) | `schools/<uuid:school_id>/attendance/summary` | `attendance_views.summary` |
| [backend/institutions/urls.py:146](../backend/institutions/urls.py#L146) | `schools/<uuid:school_id>/attendance/classes/<uuid:classroom_id>/conduct` | `conduct_views.notices` |
| [backend/institutions/urls.py:147](../backend/institutions/urls.py#L147) | `schools/<uuid:school_id>/attendance/classes/<uuid:classroom_id>/conduct/<uuid:notice_id>/withdraw` | `conduct_views.withdraw` |
| [backend/institutions/urls.py:148](../backend/institutions/urls.py#L148) | `schools/<uuid:school_id>/attendance/sessions/<uuid:session_id>` | `attendance_views.session_detail` |
| [backend/institutions/urls.py:149](../backend/institutions/urls.py#L149) | `schools/<uuid:school_id>/attendance/sessions/<uuid:session_id>/marks` | `attendance_views.record_marks` |
| [backend/institutions/urls.py:150](../backend/institutions/urls.py#L150) | `schools/<uuid:school_id>/attendance/sessions/<uuid:session_id>/close` | `attendance_views.close_session` |
| [backend/institutions/urls.py:151](../backend/institutions/urls.py#L151) | `schools/<uuid:school_id>/attendance/sessions/<uuid:session_id>/marks/<uuid:enrollment_id>/history` | `attendance_views.changes` |
| [backend/institutions/urls.py:152](../backend/institutions/urls.py#L152) | `schools/<uuid:school_id>/operating/suppliers` | `operating_views.suppliers` |
| [backend/institutions/urls.py:153](../backend/institutions/urls.py#L153) | `schools/<uuid:school_id>/operating/suppliers/<uuid:supplier_id>` | `operating_views.supplier_detail` |
| [backend/institutions/urls.py:154](../backend/institutions/urls.py#L154) | `schools/<uuid:school_id>/operating/budgets` | `operating_views.budgets` |
| [backend/institutions/urls.py:155](../backend/institutions/urls.py#L155) | `schools/<uuid:school_id>/operating/budgets/<uuid:budget_id>` | `operating_views.budget_detail` |
| [backend/institutions/urls.py:156](../backend/institutions/urls.py#L156) | `schools/<uuid:school_id>/operating/budgets/<uuid:budget_id>/approve` | `operating_views.approve_budget` |
| [backend/institutions/urls.py:157](../backend/institutions/urls.py#L157) | `schools/<uuid:school_id>/operating/expenses` | `operating_views.expenses` |
| [backend/institutions/urls.py:158](../backend/institutions/urls.py#L158) | `schools/<uuid:school_id>/operating/expenses/<uuid:expense_id>` | `operating_views.expense_detail` |
| [backend/institutions/urls.py:159](../backend/institutions/urls.py#L159) | `schools/<uuid:school_id>/operating/expenses/<uuid:expense_id>/approve` | `operating_views.approve_expense` |
| [backend/institutions/urls.py:160](../backend/institutions/urls.py#L160) | `schools/<uuid:school_id>/operating/expenses/<uuid:expense_id>/payments` | `operating_views.pay_expense` |
| [backend/institutions/urls.py:161](../backend/institutions/urls.py#L161) | `schools/<uuid:school_id>/operating/payments/<uuid:payment_id>/void` | `operating_views.void_expense_payment` |
| [backend/institutions/urls.py:162](../backend/institutions/urls.py#L162) | `schools/<uuid:school_id>/operating/summary` | `operating_views.summary` |
| [backend/institutions/urls.py:163](../backend/institutions/urls.py#L163) | `schools/<uuid:school_id>/payroll/staff` | `payroll_views.personnel` |
| [backend/institutions/urls.py:164](../backend/institutions/urls.py#L164) | `schools/<uuid:school_id>/payroll/runs` | `payroll_views.runs` |
| [backend/institutions/urls.py:165](../backend/institutions/urls.py#L165) | `schools/<uuid:school_id>/payroll/runs/<uuid:run_id>` | `payroll_views.run_detail` |
| [backend/institutions/urls.py:166](../backend/institutions/urls.py#L166) | `schools/<uuid:school_id>/payroll/runs/<uuid:run_id>/approve` | `payroll_views.approve` |
| [backend/institutions/urls.py:167](../backend/institutions/urls.py#L167) | `schools/<uuid:school_id>/payroll/runs/<uuid:run_id>/payments` | `payroll_views.pay` |
| [backend/institutions/urls.py:168](../backend/institutions/urls.py#L168) | `schools/<uuid:school_id>/payroll/payments/<uuid:payment_id>/void` | `payroll_views.void` |
| [backend/institutions/urls.py:169](../backend/institutions/urls.py#L169) | `schools/<uuid:school_id>/finance/schedules` | `finance_views.schedules` |
| [backend/institutions/urls.py:170](../backend/institutions/urls.py#L170) | `schools/<uuid:school_id>/finance/schedules/monthly` | `finance_views.generate_monthly_schedules` |
| [backend/institutions/urls.py:171](../backend/institutions/urls.py#L171) | `schools/<uuid:school_id>/finance/schedules/<uuid:schedule_id>` | `finance_views.schedule_detail` |
| [backend/institutions/urls.py:172](../backend/institutions/urls.py#L172) | `schools/<uuid:school_id>/finance/charges` | `finance_views.charges` |
| [backend/institutions/urls.py:173](../backend/institutions/urls.py#L173) | `schools/<uuid:school_id>/finance/charges/<uuid:charge_id>` | `finance_views.charge_detail` |
| [backend/institutions/urls.py:174](../backend/institutions/urls.py#L174) | `schools/<uuid:school_id>/finance/charges/<uuid:charge_id>/invoice` | `finance_views.invoice` |
| [backend/institutions/urls.py:175](../backend/institutions/urls.py#L175) | `schools/<uuid:school_id>/finance/enrollments/<uuid:enrollment_id>/notice` | `finance_extra_documents.staff_notice` |
| [backend/institutions/urls.py:176](../backend/institutions/urls.py#L176) | `schools/<uuid:school_id>/finance/payments/<uuid:payment_id>/cancellation-pdf` | `finance_extra_documents.staff_void_document` |
| [backend/institutions/urls.py:177](../backend/institutions/urls.py#L177) | `schools/<uuid:school_id>/finance/summary` | `finance_summary_views.summary` |
| [backend/institutions/urls.py:178](../backend/institutions/urls.py#L178) | `schools/<uuid:school_id>/finance/quality` | `finance_quality_views.quality` |
| [backend/institutions/urls.py:179](../backend/institutions/urls.py#L179) | `schools/<uuid:school_id>/finance/roster` | `finance_summary_views.finance_roster` |
| [backend/institutions/urls.py:180](../backend/institutions/urls.py#L180) | `schools/<uuid:school_id>/finance/payments` | `finance_views.payments` |
| [backend/institutions/urls.py:181](../backend/institutions/urls.py#L181) | `schools/<uuid:school_id>/finance/cash/closings/<uuid:closing_id>/transfers` | `finance_cash_views.cash_transfer` |
| [backend/institutions/urls.py:182](../backend/institutions/urls.py#L182) | `schools/<uuid:school_id>/finance/cash/closings/<uuid:closing_id>/transfers/<uuid:transfer_id>/approve` | `finance_cash_views.approve_transfer` |
| [backend/institutions/urls.py:183](../backend/institutions/urls.py#L183) | `schools/<uuid:school_id>/finance/cash/closings` | `finance_cash_views.cash_closings` |
| [backend/institutions/urls.py:184](../backend/institutions/urls.py#L184) | `schools/<uuid:school_id>/finance/cash/closings/<uuid:closing_id>/approve` | `finance_cash_views.approve_cash_closing` |
| [backend/institutions/urls.py:185](../backend/institutions/urls.py#L185) | `schools/<uuid:school_id>/finance/batches` | `finance_batch_views.create_batch` |
| [backend/institutions/urls.py:186](../backend/institutions/urls.py#L186) | `schools/<uuid:school_id>/finance/batches/<uuid:batch_id>` | `finance_batch_views.batch_detail` |
| [backend/institutions/urls.py:187](../backend/institutions/urls.py#L187) | `schools/<uuid:school_id>/finance/batches/<uuid:batch_id>/receipt` | `finance_batch_views.batch_receipt` |
| [backend/institutions/urls.py:188](../backend/institutions/urls.py#L188) | `schools/<uuid:school_id>/finance/payments/<uuid:payment_id>/void` | `finance_views.void_payment` |
| [backend/institutions/urls.py:189](../backend/institutions/urls.py#L189) | `schools/<uuid:school_id>/finance/payments/<uuid:payment_id>/receipt` | `finance_views.receipt` |
| [backend/institutions/urls.py:190](../backend/institutions/urls.py#L190) | `schools/<uuid:school_id>/finance/enrollments/<uuid:enrollment_id>/statement` | `finance_views.statement` |
| [backend/institutions/urls.py:191](../backend/institutions/urls.py#L191) | `schools/<uuid:school_id>/finance/enrollments/<uuid:enrollment_id>/documents` | `finance_parent_documents.staff_documents` |
| [backend/institutions/urls.py:192](../backend/institutions/urls.py#L192) | `schools/<uuid:school_id>/council-choices` | `council_views.council_choices` |
| [backend/institutions/urls.py:193](../backend/institutions/urls.py#L193) | `schools/<uuid:school_id>/councils` | `council_views.councils` |
| [backend/institutions/urls.py:194](../backend/institutions/urls.py#L194) | `schools/<uuid:school_id>/councils/<uuid:council_id>` | `council_views.council_detail` |
| [backend/institutions/urls.py:195](../backend/institutions/urls.py#L195) | `schools/<uuid:school_id>/councils/<uuid:council_id>/decisions` | `council_views.council_decisions` |
| [backend/institutions/urls.py:196](../backend/institutions/urls.py#L196) | `schools/<uuid:school_id>/councils/<uuid:council_id>/primary-passage-evidence` | `council_views.primary_passage_evidence` |
| [backend/institutions/urls.py:197](../backend/institutions/urls.py#L197) | `schools/<uuid:school_id>/councils/<uuid:council_id>/close` | `council_views.close_council` |
| [backend/institutions/urls.py:198](../backend/institutions/urls.py#L198) | `schools/<uuid:school_id>/reports/<uuid:report_id>/amendments` | `council_views.amendments` |
| [backend/institutions/urls.py:199](../backend/institutions/urls.py#L199) | `schools/<uuid:school_id>/reports/<uuid:report_id>/amendments/<uuid:amendment_id>` | `council_views.amendment_detail` |
| [backend/institutions/urls.py:200](../backend/institutions/urls.py#L200) | `schools/<uuid:school_id>/reports/<uuid:report_id>/amendments/<uuid:amendment_id>/pdf` | `council_views.amendment_pdf` |
| [backend/institutions/urls.py:201](../backend/institutions/urls.py#L201) | `schools/<uuid:school_id>/assessments/<uuid:assessment_id>/publish` | `report_views.publish_assessment` |
| [backend/institutions/urls.py:202](../backend/institutions/urls.py#L202) | `schools/<uuid:school_id>/reports` | `report_views.reports` |
| [backend/institutions/urls.py:203](../backend/institutions/urls.py#L203) | `schools/<uuid:school_id>/reports/<uuid:report_id>` | `report_views.report_detail` |
| [backend/institutions/urls.py:204](../backend/institutions/urls.py#L204) | `schools/<uuid:school_id>/reports/<uuid:report_id>/publish` | `report_views.publish_report` |
| [backend/institutions/urls.py:205](../backend/institutions/urls.py#L205) | `schools/<uuid:school_id>/reports/<uuid:report_id>/pdf` | `report_views.report_pdf` |
| [backend/institutions/urls.py:206](../backend/institutions/urls.py#L206) | `schools/<uuid:school_id>/courses/<uuid:course_id>/assessments` | `assessment_views.assessments` |
| [backend/institutions/urls.py:207](../backend/institutions/urls.py#L207) | `schools/<uuid:school_id>/assessments/<uuid:assessment_id>` | `assessment_views.assessment_detail` |
| [backend/institutions/urls.py:208](../backend/institutions/urls.py#L208) | `schools/<uuid:school_id>/assessments/<uuid:assessment_id>/roster` | `assessment_views.roster` |
| [backend/institutions/urls.py:209](../backend/institutions/urls.py#L209) | `schools/<uuid:school_id>/assessments/<uuid:assessment_id>/grades` | `assessment_views.grades` |
| [backend/institutions/urls.py:210](../backend/institutions/urls.py#L210) | `schools/<uuid:school_id>/assessments/<uuid:assessment_id>/grades/batch` | `assessment_views.grade_batch` |
| [backend/institutions/urls.py:211](../backend/institutions/urls.py#L211) | `schools/<uuid:school_id>/courses/<uuid:course_id>/averages` | `assessment_views.course_averages` |
| [backend/institutions/urls.py:212](../backend/institutions/urls.py#L212) | `schools/<uuid:school_id>/assessments/<uuid:assessment_id>/grades/<uuid:grade_id>` | `assessment_views.grade_detail` |
| [backend/institutions/urls.py:213](../backend/institutions/urls.py#L213) | `schools/<uuid:school_id>/subjects` | `curriculum_views.subjects` |
| [backend/institutions/urls.py:214](../backend/institutions/urls.py#L214) | `schools/<uuid:school_id>/subjects/<uuid:subject_id>` | `curriculum_views.subject_detail` |
| [backend/institutions/urls.py:215](../backend/institutions/urls.py#L215) | `schools/<uuid:school_id>/courses` | `curriculum_views.courses` |
| [backend/institutions/urls.py:216](../backend/institutions/urls.py#L216) | `schools/<uuid:school_id>/diary/courses` | `teaching_diary_views.catalog` |
| [backend/institutions/urls.py:217](../backend/institutions/urls.py#L217) | `schools/<uuid:school_id>/diary/courses/<uuid:course_id>` | `teaching_diary_views.diary` |
| [backend/institutions/urls.py:218](../backend/institutions/urls.py#L218) | `schools/<uuid:school_id>/diary/courses/<uuid:course_id>/progress` | `course_progress_views.progress` |
| [backend/institutions/urls.py:219](../backend/institutions/urls.py#L219) | `schools/<uuid:school_id>/diary/courses/<uuid:course_id>/remediation` | `remediation_views.remediation` |
| [backend/institutions/urls.py:220](../backend/institutions/urls.py#L220) | `schools/<uuid:school_id>/diary/entries/<uuid:entry_id>/resources` | `diary_resource_views.resources` |
| [backend/institutions/urls.py:221](../backend/institutions/urls.py#L221) | `schools/<uuid:school_id>/diary/entries/<uuid:entry_id>/resources/<uuid:resource_id>` | `diary_resource_views.resource_detail` |
| [backend/institutions/urls.py:222](../backend/institutions/urls.py#L222) | `schools/<uuid:school_id>/curriculum/my-courses` | `curriculum_views.my_courses` |
| [backend/institutions/urls.py:223](../backend/institutions/urls.py#L223) | `schools/<uuid:school_id>/courses/generate` | `curriculum_views.generate_courses` |
| [backend/institutions/urls.py:224](../backend/institutions/urls.py#L224) | `schools/<uuid:school_id>/courses/<uuid:course_id>` | `curriculum_views.course_detail` |
| [backend/institutions/urls.py:225](../backend/institutions/urls.py#L225) | `schools/<uuid:school_id>/courses/<uuid:course_id>/units` | `curriculum_views.units` |
| [backend/institutions/urls.py:226](../backend/institutions/urls.py#L226) | `schools/<uuid:school_id>/courses/<uuid:course_id>/units/<uuid:unit_id>` | `curriculum_views.unit_detail` |
| [backend/institutions/urls.py:227](../backend/institutions/urls.py#L227) | `schools/<uuid:school_id>/courses/<uuid:course_id>/instructors` | `curriculum_views.instructors` |
| [backend/institutions/urls.py:228](../backend/institutions/urls.py#L228) | `schools/<uuid:school_id>/courses/<uuid:course_id>/instructors/<uuid:instructor_id>` | `curriculum_views.instructor_detail` |
| [backend/institutions/urls.py:229](../backend/institutions/urls.py#L229) | `schools/<uuid:school_id>/organization/positions` | `organization_views.positions` |
| [backend/institutions/urls.py:230](../backend/institutions/urls.py#L230) | `schools/<uuid:school_id>/organization/appointments` | `organization_views.appointments` |
| [backend/institutions/urls.py:231](../backend/institutions/urls.py#L231) | `schools/<uuid:school_id>/organization/appointments/<uuid:appointment_id>` | `organization_views.appointment_detail` |
| [backend/institutions/urls.py:232](../backend/institutions/urls.py#L232) | `schools/<uuid:school_id>/organization/my-appointments` | `organization_views.my_appointments` |
| [backend/institutions/urls.py:233](../backend/institutions/urls.py#L233) | `schools/<uuid:school_id>/staff/onboard` | `staff_onboarding_views.onboard_staff` |
| [backend/institutions/urls.py:234](../backend/institutions/urls.py#L234) | `schools/<uuid:school_id>/members/<uuid:member_id>/cycle-access` | `cycle_access_views.member_cycle_access` |
| [backend/institutions/urls.py:235](../backend/institutions/urls.py#L235) | `schools/<uuid:school_id>/staff` | `staff_views.staff` |
| [backend/institutions/urls.py:236](../backend/institutions/urls.py#L236) | `schools/<uuid:school_id>/staff/me/assignments` | `staff_views.my_assignments` |
| [backend/institutions/urls.py:237](../backend/institutions/urls.py#L237) | `schools/<uuid:school_id>/staff/me/profile` | `staff_profile_views.my_profile` |
| [backend/institutions/urls.py:238](../backend/institutions/urls.py#L238) | `schools/<uuid:school_id>/staff/me/dossier` | `staff_dossier_views.my_staff_dossier` |
| [backend/institutions/urls.py:239](../backend/institutions/urls.py#L239) | `schools/<uuid:school_id>/staff/<uuid:staff_id>/dossier` | `staff_dossier_views.staff_dossier` |
| [backend/institutions/urls.py:240](../backend/institutions/urls.py#L240) | `schools/<uuid:school_id>/staff/<uuid:staff_id>/photo` | `staff_profile_views.staff_photo` |
| [backend/institutions/urls.py:241](../backend/institutions/urls.py#L241) | `schools/<uuid:school_id>/staff/<uuid:staff_id>` | `staff_views.staff_detail` |
| [backend/institutions/urls.py:242](../backend/institutions/urls.py#L242) | `schools/<uuid:school_id>/staff-assignments` | `staff_views.assignments` |
| [backend/institutions/urls.py:243](../backend/institutions/urls.py#L243) | `schools/<uuid:school_id>/staff-assignments/<uuid:assignment_id>` | `staff_views.assignment_detail` |
| [backend/institutions/urls.py:244](../backend/institutions/urls.py#L244) | `schools/<uuid:school_id>/overview/students` | `overview_views.students_overview` |
| [backend/institutions/urls.py:245](../backend/institutions/urls.py#L245) | `schools/<uuid:school_id>/overview/classes` | `registration_views.classes_overview` |
| [backend/institutions/urls.py:246](../backend/institutions/urls.py#L246) | `schools/<uuid:school_id>/enrollment-form` | `enrollment_form.enrollment_form` |
| [backend/institutions/urls.py:247](../backend/institutions/urls.py#L247) | `schools/<uuid:school_id>/students/register` | `registration_views.register_student` |
| [backend/institutions/urls.py:248](../backend/institutions/urls.py#L248) | `schools/<uuid:school_id>/students/next-code` | `registration_views.next_code` |
| [backend/institutions/urls.py:249](../backend/institutions/urls.py#L249) | `schools/<uuid:school_id>/students/<uuid:student_id>/transfer` | `student_transfers.issue` |
| [backend/institutions/urls.py:250](../backend/institutions/urls.py#L250) | `schools/<uuid:school_id>/students/<uuid:student_id>/dossier` | `registration_views.student_dossier` |
| [backend/institutions/urls.py:251](../backend/institutions/urls.py#L251) | `schools/<uuid:school_id>/classes/<uuid:class_id>/students` | `registration_views.class_students` |
| [backend/institutions/urls.py:252](../backend/institutions/urls.py#L252) | `schools/<uuid:school_id>/classes/<uuid:class_id>/enroll` | `registration_views.class_enroll` |
| [backend/institutions/urls.py:253](../backend/institutions/urls.py#L253) | `schools/<uuid:school_id>/classes/<uuid:class_id>/apply-fees` | `registration_views.class_apply_fees` |
| [backend/institutions/urls.py:254](../backend/institutions/urls.py#L254) | `schools/<uuid:school_id>/academic/quick-classes` | `registration_views.quick_classes` |
| [backend/institutions/urls.py:255](../backend/institutions/urls.py#L255) | `schools/<uuid:school_id>/academic/preschool-standard-classes` | `registration_views.standard_preschool_classes` |
| [backend/institutions/urls.py:256](../backend/institutions/urls.py#L256) | `schools/<uuid:school_id>/academic/standard-classes` | `registration_views.standard_school_classes` |
| [backend/institutions/urls.py:257](../backend/institutions/urls.py#L257) | `schools/<uuid:school_id>/academic/series-classes` | `secondary_views.series_classes` |
| [backend/institutions/urls.py:258](../backend/institutions/urls.py#L258) | `schools/<uuid:school_id>/academic/classes/<uuid:class_id>/carry-forward` | `secondary_views.carry_forward_class` |
| [backend/institutions/urls.py:259](../backend/institutions/urls.py#L259) | `schools/<uuid:school_id>/academic/classes/<uuid:class_id>/clone` | `registration_views.clone_class` |
| [backend/institutions/urls.py:260](../backend/institutions/urls.py#L260) | `schools/<uuid:school_id>/overview/finance` | `overview_views.finance_overview` |
| [backend/institutions/urls.py:261](../backend/institutions/urls.py#L261) | `schools/<uuid:school_id>/students` | `student_views.students` |
| [backend/institutions/urls.py:262](../backend/institutions/urls.py#L262) | `schools/<uuid:school_id>/students/<uuid:student_id>` | `student_views.student_detail` |
| [backend/institutions/urls.py:263](../backend/institutions/urls.py#L263) | `schools/<uuid:school_id>/guardians-by-class` | `student_views.guardians_by_class` |
| [backend/institutions/urls.py:264](../backend/institutions/urls.py#L264) | `schools/<uuid:school_id>/students/<uuid:student_id>/guardians` | `student_views.guardians` |
| [backend/institutions/urls.py:265](../backend/institutions/urls.py#L265) | `schools/<uuid:school_id>/students/<uuid:student_id>/guardians/<uuid:guardian_id>` | `student_views.guardian_detail` |
| [backend/institutions/urls.py:266](../backend/institutions/urls.py#L266) | `schools/<uuid:school_id>/enrollments` | `student_views.enrollments` |
| [backend/institutions/urls.py:267](../backend/institutions/urls.py#L267) | `schools/<uuid:school_id>/enrollments/<uuid:enrollment_id>` | `student_views.enrollment_detail` |
| [backend/institutions/urls.py:268](../backend/institutions/urls.py#L268) | `schools/<uuid:school_id>/enrollments/<uuid:enrollment_id>/assignment` | `class_assignment_views.assignment` |
| [backend/institutions/urls.py:269](../backend/institutions/urls.py#L269) | `schools/<uuid:school_id>/enrollments/<uuid:enrollment_id>/history` | `student_views.enrollment_history` |
| [backend/institutions/urls.py:270](../backend/institutions/urls.py#L270) | `schools/<uuid:school_id>/academic/annual-snapshot` | `annual_views.annual_snapshot` |
| [backend/institutions/urls.py:271](../backend/institutions/urls.py#L271) | `schools/<uuid:school_id>/academic/pedagogical-calendar` | `calendar_views.events` |
| [backend/institutions/urls.py:272](../backend/institutions/urls.py#L272) | `schools/<uuid:school_id>/academic/preschool-followup` | `preschool_followup_views.followup` |
| [backend/institutions/urls.py:273](../backend/institutions/urls.py#L273) | `schools/<uuid:school_id>/academic/primary-criteria` | `primary_views.criteria` |
| [backend/institutions/urls.py:274](../backend/institutions/urls.py#L274) | `schools/<uuid:school_id>/academic/primary-mastery` | `primary_views.mastery` |
| [backend/institutions/urls.py:275](../backend/institutions/urls.py#L275) | `schools/<uuid:school_id>/academic/pedagogical-calendar/<uuid:event_id>` | `calendar_views.event_detail` |
| [backend/institutions/urls.py:276](../backend/institutions/urls.py#L276) | `schools/<uuid:school_id>/academic/pedagogical-calendar/profile` | `calendar_views.update_profile` |
| [backend/institutions/urls.py:277](../backend/institutions/urls.py#L277) | `schools/<uuid:school_id>/academic/years/<uuid:year_id>/activate` | `annual_views.activate_year` |
| [backend/institutions/urls.py:278](../backend/institutions/urls.py#L278) | `schools/<uuid:school_id>/academic/years/<uuid:year_id>/closure-review` | `annual_views.closure_review` |
| [backend/institutions/urls.py:279](../backend/institutions/urls.py#L279) | `schools/<uuid:school_id>/academic/years/<uuid:year_id>/close` | `annual_views.close_year` |
| [backend/institutions/urls.py:280](../backend/institutions/urls.py#L280) | `schools/<uuid:school_id>/academic/prepare-year` | `annual_views.prepare_year` |
| [backend/institutions/urls.py:281](../backend/institutions/urls.py#L281) | `schools/<uuid:school_id>/academic/<str:resource>` | `academic_views.collection` |
| [backend/institutions/urls.py:282](../backend/institutions/urls.py#L282) | `schools/<uuid:school_id>/academic/<str:resource>/<uuid:object_id>` | `academic_views.detail` |
| [backend/institutions/urls.py:283](../backend/institutions/urls.py#L283) | `organizations` | `views.organizations` |
| [backend/institutions/urls.py:284](../backend/institutions/urls.py#L284) | `organizations/<uuid:organization_id>/schools` | `views.organization_schools` |
| [backend/institutions/urls.py:285](../backend/institutions/urls.py#L285) | `schools` | `views.schools` |
| [backend/institutions/urls.py:286](../backend/institutions/urls.py#L286) | `schools/<uuid:school_id>` | `views.school_detail` |
| [backend/institutions/urls.py:287](../backend/institutions/urls.py#L287) | `schools/<uuid:school_id>/my-access` | `views.my_school_access` |
| [backend/institutions/urls.py:288](../backend/institutions/urls.py#L288) | `schools/<uuid:school_id>/users` | `views.school_user_create` |
| [backend/institutions/urls.py:289](../backend/institutions/urls.py#L289) | `schools/<uuid:school_id>/members` | `views.school_members` |
| [backend/institutions/urls.py:290](../backend/institutions/urls.py#L290) | `schools/<uuid:school_id>/roles` | `views.school_roles` |
| [backend/institutions/urls.py:291](../backend/institutions/urls.py#L291) | `schools/<uuid:school_id>/roles/<uuid:role_id>` | `views.school_role_detail` |
| [backend/institutions/urls.py:292](../backend/institutions/urls.py#L292) | `schools/<uuid:school_id>/settings` | `views.school_settings` |
| [backend/institutions/urls.py:293](../backend/institutions/urls.py#L293) | `schools/<uuid:school_id>/audit` | `views.school_audit` |

## Serveur recensé

- [backend/accounts/__init__.py](../backend/accounts/__init__.py)
- [backend/accounts/email_backends.py](../backend/accounts/email_backends.py)
- [backend/accounts/management/__init__.py](../backend/accounts/management/__init__.py)
- [backend/accounts/management/commands/__init__.py](../backend/accounts/management/commands/__init__.py)
- [backend/accounts/management/commands/bootstrap_platform_admin.py](../backend/accounts/management/commands/bootstrap_platform_admin.py)
- [backend/accounts/models.py](../backend/accounts/models.py)
- [backend/accounts/parent_signup_views.py](../backend/accounts/parent_signup_views.py)
- [backend/accounts/password_admin_views.py](../backend/accounts/password_admin_views.py)
- [backend/accounts/qr.py](../backend/accounts/qr.py)
- [backend/accounts/security.py](../backend/accounts/security.py)
- [backend/accounts/urls.py](../backend/accounts/urls.py)
- [backend/accounts/views.py](../backend/accounts/views.py)
- [backend/conduct/__init__.py](../backend/conduct/__init__.py)
- [backend/conduct/models.py](../backend/conduct/models.py)
- [backend/conduct/views.py](../backend/conduct/views.py)
- [backend/config/__init__.py](../backend/config/__init__.py)
- [backend/config/middleware.py](../backend/config/middleware.py)
- [backend/config/settings.py](../backend/config/settings.py)
- [backend/config/urls.py](../backend/config/urls.py)
- [backend/config/wsgi.py](../backend/config/wsgi.py)
- [backend/institutions/__init__.py](../backend/institutions/__init__.py)
- [backend/institutions/academic_models.py](../backend/institutions/academic_models.py)
- [backend/institutions/academic_views.py](../backend/institutions/academic_views.py)
- [backend/institutions/admission_cash_views.py](../backend/institutions/admission_cash_views.py)
- [backend/institutions/admission_finance.py](../backend/institutions/admission_finance.py)
- [backend/institutions/admission_finance_views.py](../backend/institutions/admission_finance_views.py)
- [backend/institutions/admission_models.py](../backend/institutions/admission_models.py)
- [backend/institutions/admission_policy.py](../backend/institutions/admission_policy.py)
- [backend/institutions/admission_route_views.py](../backend/institutions/admission_route_views.py)
- [backend/institutions/admission_scholarship_amounts.py](../backend/institutions/admission_scholarship_amounts.py)
- [backend/institutions/admission_views.py](../backend/institutions/admission_views.py)
- [backend/institutions/annual_views.py](../backend/institutions/annual_views.py)
- [backend/institutions/assessment_models.py](../backend/institutions/assessment_models.py)
- [backend/institutions/assessment_views.py](../backend/institutions/assessment_views.py)
- [backend/institutions/attendance_models.py](../backend/institutions/attendance_models.py)
- [backend/institutions/attendance_views.py](../backend/institutions/attendance_views.py)
- [backend/institutions/calendar_views.py](../backend/institutions/calendar_views.py)
- [backend/institutions/class_assignment_views.py](../backend/institutions/class_assignment_views.py)
- [backend/institutions/council_models.py](../backend/institutions/council_models.py)
- [backend/institutions/council_views.py](../backend/institutions/council_views.py)
- [backend/institutions/course_progress_models.py](../backend/institutions/course_progress_models.py)
- [backend/institutions/course_progress_views.py](../backend/institutions/course_progress_views.py)
- [backend/institutions/curriculum_models.py](../backend/institutions/curriculum_models.py)
- [backend/institutions/curriculum_views.py](../backend/institutions/curriculum_views.py)
- [backend/institutions/cycle_access_views.py](../backend/institutions/cycle_access_views.py)
- [backend/institutions/cycle_scope.py](../backend/institutions/cycle_scope.py)
- [backend/institutions/delegation_views.py](../backend/institutions/delegation_views.py)
- [backend/institutions/demo_payment_views.py](../backend/institutions/demo_payment_views.py)
- [backend/institutions/diary_resource_models.py](../backend/institutions/diary_resource_models.py)
- [backend/institutions/diary_resource_views.py](../backend/institutions/diary_resource_views.py)
- [backend/institutions/enrollment_form.py](../backend/institutions/enrollment_form.py)
- [backend/institutions/family_notification_models.py](../backend/institutions/family_notification_models.py)
- [backend/institutions/family_notification_views.py](../backend/institutions/family_notification_views.py)
- [backend/institutions/finance_batch_views.py](../backend/institutions/finance_batch_views.py)
- [backend/institutions/finance_cash_policy.py](../backend/institutions/finance_cash_policy.py)
- [backend/institutions/finance_cash_views.py](../backend/institutions/finance_cash_views.py)
- [backend/institutions/finance_document_pdf.py](../backend/institutions/finance_document_pdf.py)
- [backend/institutions/finance_evidence.py](../backend/institutions/finance_evidence.py)
- [backend/institutions/finance_extra_documents.py](../backend/institutions/finance_extra_documents.py)
- [backend/institutions/finance_models.py](../backend/institutions/finance_models.py)
- [backend/institutions/finance_parent_documents.py](../backend/institutions/finance_parent_documents.py)
- [backend/institutions/finance_payment_order.py](../backend/institutions/finance_payment_order.py)
- [backend/institutions/finance_quality_views.py](../backend/institutions/finance_quality_views.py)
- [backend/institutions/finance_summary_views.py](../backend/institutions/finance_summary_views.py)
- [backend/institutions/finance_views.py](../backend/institutions/finance_views.py)
- [backend/institutions/import_models.py](../backend/institutions/import_models.py)
- [backend/institutions/import_service.py](../backend/institutions/import_service.py)
- [backend/institutions/import_views.py](../backend/institutions/import_views.py)
- [backend/institutions/management/__init__.py](../backend/institutions/management/__init__.py)
- [backend/institutions/management/commands/__init__.py](../backend/institutions/management/commands/__init__.py)
- [backend/institutions/management/commands/audit_yem_foundations.py](../backend/institutions/management/commands/audit_yem_foundations.py)
- [backend/institutions/management/commands/yem_send_parent_push.py](../backend/institutions/management/commands/yem_send_parent_push.py)
- [backend/institutions/models.py](../backend/institutions/models.py)
- [backend/institutions/operating_models.py](../backend/institutions/operating_models.py)
- [backend/institutions/operating_views.py](../backend/institutions/operating_views.py)
- [backend/institutions/organization_models.py](../backend/institutions/organization_models.py)
- [backend/institutions/organization_views.py](../backend/institutions/organization_views.py)
- [backend/institutions/overview_views.py](../backend/institutions/overview_views.py)
- [backend/institutions/owner_overview_views.py](../backend/institutions/owner_overview_views.py)
- [backend/institutions/parent_admission_models.py](../backend/institutions/parent_admission_models.py)
- [backend/institutions/parent_admission_views.py](../backend/institutions/parent_admission_views.py)
- [backend/institutions/parent_dossier_views.py](../backend/institutions/parent_dossier_views.py)
- [backend/institutions/parent_existing_models.py](../backend/institutions/parent_existing_models.py)
- [backend/institutions/parent_existing_views.py](../backend/institutions/parent_existing_views.py)
- [backend/institutions/parent_listing_policy.py](../backend/institutions/parent_listing_policy.py)
- [backend/institutions/parent_models.py](../backend/institutions/parent_models.py)
- [backend/institutions/parent_payment_models.py](../backend/institutions/parent_payment_models.py)
- [backend/institutions/parent_payment_service.py](../backend/institutions/parent_payment_service.py)
- [backend/institutions/parent_payment_views.py](../backend/institutions/parent_payment_views.py)
- [backend/institutions/parent_push_delivery.py](../backend/institutions/parent_push_delivery.py)
- [backend/institutions/parent_push_models.py](../backend/institutions/parent_push_models.py)
- [backend/institutions/parent_push_sources.py](../backend/institutions/parent_push_sources.py)
- [backend/institutions/parent_push_transport.py](../backend/institutions/parent_push_transport.py)
- [backend/institutions/parent_push_views.py](../backend/institutions/parent_push_views.py)
- [backend/institutions/parent_views.py](../backend/institutions/parent_views.py)
- [backend/institutions/payroll_models.py](../backend/institutions/payroll_models.py)
- [backend/institutions/payroll_views.py](../backend/institutions/payroll_views.py)
- [backend/institutions/pedagogical_family_notices.py](../backend/institutions/pedagogical_family_notices.py)
- [backend/institutions/phone_utils.py](../backend/institutions/phone_utils.py)
- [backend/institutions/platform_admin_views.py](../backend/institutions/platform_admin_views.py)
- [backend/institutions/platform_views.py](../backend/institutions/platform_views.py)
- [backend/institutions/preschool_classes.py](../backend/institutions/preschool_classes.py)
- [backend/institutions/preschool_followup_models.py](../backend/institutions/preschool_followup_models.py)
- [backend/institutions/preschool_followup_views.py](../backend/institutions/preschool_followup_views.py)
- [backend/institutions/primary_models.py](../backend/institutions/primary_models.py)
- [backend/institutions/primary_views.py](../backend/institutions/primary_views.py)
- [backend/institutions/registration_views.py](../backend/institutions/registration_views.py)
- [backend/institutions/remediation_models.py](../backend/institutions/remediation_models.py)
- [backend/institutions/remediation_views.py](../backend/institutions/remediation_views.py)
- [backend/institutions/report_engine.py](../backend/institutions/report_engine.py)
- [backend/institutions/report_models.py](../backend/institutions/report_models.py)
- [backend/institutions/report_views.py](../backend/institutions/report_views.py)
- [backend/institutions/school_branding_views.py](../backend/institutions/school_branding_views.py)
- [backend/institutions/school_functions.py](../backend/institutions/school_functions.py)
- [backend/institutions/school_governance.py](../backend/institutions/school_governance.py)
- [backend/institutions/school_profiles.py](../backend/institutions/school_profiles.py)
- [backend/institutions/secondary_series.py](../backend/institutions/secondary_series.py)
- [backend/institutions/secondary_views.py](../backend/institutions/secondary_views.py)
- [backend/institutions/services.py](../backend/institutions/services.py)
- [backend/institutions/singpay_models.py](../backend/institutions/singpay_models.py)
- [backend/institutions/singpay_service.py](../backend/institutions/singpay_service.py)
- [backend/institutions/singpay_views.py](../backend/institutions/singpay_views.py)
- [backend/institutions/staff_dossier_views.py](../backend/institutions/staff_dossier_views.py)
- [backend/institutions/staff_models.py](../backend/institutions/staff_models.py)
- [backend/institutions/staff_onboarding_views.py](../backend/institutions/staff_onboarding_views.py)
- [backend/institutions/staff_profile_models.py](../backend/institutions/staff_profile_models.py)
- [backend/institutions/staff_profile_views.py](../backend/institutions/staff_profile_views.py)
- [backend/institutions/staff_views.py](../backend/institutions/staff_views.py)
- [backend/institutions/standard_classes.py](../backend/institutions/standard_classes.py)
- [backend/institutions/student_access.py](../backend/institutions/student_access.py)
- [backend/institutions/student_models.py](../backend/institutions/student_models.py)
- [backend/institutions/student_numbering.py](../backend/institutions/student_numbering.py)
- [backend/institutions/student_numbering_views.py](../backend/institutions/student_numbering_views.py)
- [backend/institutions/student_transfers.py](../backend/institutions/student_transfers.py)
- [backend/institutions/student_views.py](../backend/institutions/student_views.py)
- [backend/institutions/subscription_access.py](../backend/institutions/subscription_access.py)
- [backend/institutions/subscription_amendments.py](../backend/institutions/subscription_amendments.py)
- [backend/institutions/subscription_dashboard.py](../backend/institutions/subscription_dashboard.py)
- [backend/institutions/subscription_document_pdf.py](../backend/institutions/subscription_document_pdf.py)
- [backend/institutions/subscription_models.py](../backend/institutions/subscription_models.py)
- [backend/institutions/subscription_pricing.py](../backend/institutions/subscription_pricing.py)
- [backend/institutions/subscription_reminders.py](../backend/institutions/subscription_reminders.py)
- [backend/institutions/subscription_views.py](../backend/institutions/subscription_views.py)
- [backend/institutions/teaching_diary_models.py](../backend/institutions/teaching_diary_models.py)
- [backend/institutions/teaching_diary_views.py](../backend/institutions/teaching_diary_views.py)
- [backend/institutions/timetable_models.py](../backend/institutions/timetable_models.py)
- [backend/institutions/timetable_views.py](../backend/institutions/timetable_views.py)
- [backend/institutions/urls.py](../backend/institutions/urls.py)
- [backend/institutions/views.py](../backend/institutions/views.py)
- [backend/institutions/year_closure.py](../backend/institutions/year_closure.py)
- [backend/manage.py](../backend/manage.py)
- [backend/pedagogy/__init__.py](../backend/pedagogy/__init__.py)
- [backend/pedagogy/domain.py](../backend/pedagogy/domain.py)
- [backend/pedagogy/pwa_views.py](../backend/pedagogy/pwa_views.py)
- [backend/pedagogy/views.py](../backend/pedagogy/views.py)

## Tests recensés

- [frontend/AcademicPanel.test.jsx](../frontend/AcademicPanel.test.jsx)
- [frontend/AdminPasswordReset.test.jsx](../frontend/AdminPasswordReset.test.jsx)
- [frontend/AdmissionCashDesk.test.jsx](../frontend/AdmissionCashDesk.test.jsx)
- [frontend/AdmissionFinance.test.jsx](../frontend/AdmissionFinance.test.jsx)
- [frontend/AdmissionRoutesPanel.test.jsx](../frontend/AdmissionRoutesPanel.test.jsx)
- [frontend/AdmissionsPanel.test.jsx](../frontend/AdmissionsPanel.test.jsx)
- [frontend/AnnualWorkspace.test.jsx](../frontend/AnnualWorkspace.test.jsx)
- [frontend/App.test.jsx](../frontend/App.test.jsx)
- [frontend/AuthPanel.test.jsx](../frontend/AuthPanel.test.jsx)
- [frontend/CashClosingPanel.test.jsx](../frontend/CashClosingPanel.test.jsx)
- [frontend/ClassAssignment.test.jsx](../frontend/ClassAssignment.test.jsx)
- [frontend/ClassSetup.test.jsx](../frontend/ClassSetup.test.jsx)
- [frontend/ClassWorkspace.test.jsx](../frontend/ClassWorkspace.test.jsx)
- [frontend/CommercialSimulator.test.jsx](../frontend/CommercialSimulator.test.jsx)
- [frontend/ContextJourneys.test.jsx](../frontend/ContextJourneys.test.jsx)
- [frontend/ContextMenu.test.jsx](../frontend/ContextMenu.test.jsx)
- [frontend/ContextMenuHardening.test.jsx](../frontend/ContextMenuHardening.test.jsx)
- [frontend/CourseProgress.test.jsx](../frontend/CourseProgress.test.jsx)
- [frontend/CurriculumPanel.test.jsx](../frontend/CurriculumPanel.test.jsx)
- [frontend/CycleScopeManager.test.jsx](../frontend/CycleScopeManager.test.jsx)
- [frontend/demo-api-sandbox.test.js](../frontend/demo-api-sandbox.test.js)
- [frontend/DemoExperience.test.jsx](../frontend/DemoExperience.test.jsx)
- [frontend/FinancePermissions.test.jsx](../frontend/FinancePermissions.test.jsx)
- [frontend/LegacyApp.test.jsx](../frontend/LegacyApp.test.jsx)
- [frontend/LiveFinance.test.jsx](../frontend/LiveFinance.test.jsx)
- [frontend/MonthlyTariffSetup.test.jsx](../frontend/MonthlyTariffSetup.test.jsx)
- [frontend/OperatingPanel.test.jsx](../frontend/OperatingPanel.test.jsx)
- [frontend/OwnerDashboard.test.jsx](../frontend/OwnerDashboard.test.jsx)
- [frontend/ParentAccess.test.jsx](../frontend/ParentAccess.test.jsx)
- [frontend/ParentDiscovery.test.jsx](../frontend/ParentDiscovery.test.jsx)
- [frontend/ParentExistingSchool.test.jsx](../frontend/ParentExistingSchool.test.jsx)
- [frontend/ParentSchoolRecord.test.jsx](../frontend/ParentSchoolRecord.test.jsx)
- [frontend/PayrollPanel.test.jsx](../frontend/PayrollPanel.test.jsx)
- [frontend/PedagogicalCalendar.test.jsx](../frontend/PedagogicalCalendar.test.jsx)
- [frontend/PlatformConsole.test.jsx](../frontend/PlatformConsole.test.jsx)
- [frontend/PlatformSubscriptions.test.jsx](../frontend/PlatformSubscriptions.test.jsx)
- [frontend/PreschoolFollowup.test.jsx](../frontend/PreschoolFollowup.test.jsx)
- [frontend/PrimaryCriteria.test.jsx](../frontend/PrimaryCriteria.test.jsx)
- [frontend/PrimaryMastery.test.jsx](../frontend/PrimaryMastery.test.jsx)
- [frontend/RealDemoExperience.test.jsx](../frontend/RealDemoExperience.test.jsx)
- [frontend/SchoolBrandingSettings.test.jsx](../frontend/SchoolBrandingSettings.test.jsx)
- [frontend/SchoolDashboardHeader.test.jsx](../frontend/SchoolDashboardHeader.test.jsx)
- [frontend/SchoolNotificationCenter.test.jsx](../frontend/SchoolNotificationCenter.test.jsx)
- [frontend/SecondaryMastery.test.jsx](../frontend/SecondaryMastery.test.jsx)
- [frontend/SingPayControl.test.jsx](../frontend/SingPayControl.test.jsx)
- [frontend/SingPayPayment.test.jsx](../frontend/SingPayPayment.test.jsx)
- [frontend/StaffDirectory.test.jsx](../frontend/StaffDirectory.test.jsx)
- [frontend/StaffOnboarding.test.jsx](../frontend/StaffOnboarding.test.jsx)
- [frontend/StaffProfessionalDossier.test.jsx](../frontend/StaffProfessionalDossier.test.jsx)
- [frontend/StudentPanel.test.jsx](../frontend/StudentPanel.test.jsx)
- [frontend/teacher-access.test.js](../frontend/teacher-access.test.js)
- [frontend/TeacherAssessmentAccess.test.jsx](../frontend/TeacherAssessmentAccess.test.jsx)
- [frontend/TeacherMobileFit.test.js](../frontend/TeacherMobileFit.test.js)
- [frontend/TeacherMobileTeaching.test.jsx](../frontend/TeacherMobileTeaching.test.jsx)
- [frontend/TeacherProfile.test.jsx](../frontend/TeacherProfile.test.jsx)
- [frontend/TeachingDiary.test.jsx](../frontend/TeachingDiary.test.jsx)
- [frontend/YearContext.test.jsx](../frontend/YearContext.test.jsx)
- [backend/accounts/test_admin_password_reset.py](../backend/accounts/test_admin_password_reset.py)
- [backend/accounts/test_bootstrap.py](../backend/accounts/test_bootstrap.py)
- [backend/accounts/test_email_backend_https.py](../backend/accounts/test_email_backend_https.py)
- [backend/accounts/test_parent_signup.py](../backend/accounts/test_parent_signup.py)
- [backend/accounts/tests.py](../backend/accounts/tests.py)
- [backend/institutions/test_academic.py](../backend/institutions/test_academic.py)
- [backend/institutions/test_admission_finance_scholarships.py](../backend/institutions/test_admission_finance_scholarships.py)
- [backend/institutions/test_admissions.py](../backend/institutions/test_admissions.py)
- [backend/institutions/test_assessments.py](../backend/institutions/test_assessments.py)
- [backend/institutions/test_attendance.py](../backend/institutions/test_attendance.py)
- [backend/institutions/test_class_roster_roles.py](../backend/institutions/test_class_roster_roles.py)
- [backend/institutions/test_concurrent_writes.py](../backend/institutions/test_concurrent_writes.py)
- [backend/institutions/test_councils.py](../backend/institutions/test_councils.py)
- [backend/institutions/test_curriculum.py](../backend/institutions/test_curriculum.py)
- [backend/institutions/test_cycle_scoped_staff.py](../backend/institutions/test_cycle_scoped_staff.py)
- [backend/institutions/test_database_rls.py](../backend/institutions/test_database_rls.py)
- [backend/institutions/test_demo_payment_journeys.py](../backend/institutions/test_demo_payment_journeys.py)
- [backend/institutions/test_direction_rights.py](../backend/institutions/test_direction_rights.py)
- [backend/institutions/test_director_label.py](../backend/institutions/test_director_label.py)
- [backend/institutions/test_export.py](../backend/institutions/test_export.py)
- [backend/institutions/test_family_notifications.py](../backend/institutions/test_family_notifications.py)
- [backend/institutions/test_finance.py](../backend/institutions/test_finance.py)
- [backend/institutions/test_finance_batch.py](../backend/institutions/test_finance_batch.py)
- [backend/institutions/test_finance_controls.py](../backend/institutions/test_finance_controls.py)
- [backend/institutions/test_finance_role_boundary.py](../backend/institutions/test_finance_role_boundary.py)
- [backend/institutions/test_foundation_audit.py](../backend/institutions/test_foundation_audit.py)
- [backend/institutions/test_full_journey.py](../backend/institutions/test_full_journey.py)
- [backend/institutions/test_imports.py](../backend/institutions/test_imports.py)
- [backend/institutions/test_lycee2_parent_journey.py](../backend/institutions/test_lycee2_parent_journey.py)
- [backend/institutions/test_m0_trigger_security.py](../backend/institutions/test_m0_trigger_security.py)
- [backend/institutions/test_m1_account_cycle_scope.py](../backend/institutions/test_m1_account_cycle_scope.py)
- [backend/institutions/test_m2_9_three_school_persona.py](../backend/institutions/test_m2_9_three_school_persona.py)
- [backend/institutions/test_m2_class_assignments.py](../backend/institutions/test_m2_class_assignments.py)
- [backend/institutions/test_m2_student_input_validation.py](../backend/institutions/test_m2_student_input_validation.py)
- [backend/institutions/test_operating.py](../backend/institutions/test_operating.py)
- [backend/institutions/test_organization.py](../backend/institutions/test_organization.py)
- [backend/institutions/test_overview.py](../backend/institutions/test_overview.py)
- [backend/institutions/test_owner_overview.py](../backend/institutions/test_owner_overview.py)
- [backend/institutions/test_parent_admissions.py](../backend/institutions/test_parent_admissions.py)
- [backend/institutions/test_parent_existing_links.py](../backend/institutions/test_parent_existing_links.py)
- [backend/institutions/test_parent_payments.py](../backend/institutions/test_parent_payments.py)
- [backend/institutions/test_parent_portal.py](../backend/institutions/test_parent_portal.py)
- [backend/institutions/test_parent_push.py](../backend/institutions/test_parent_push.py)
- [backend/institutions/test_parent_push_delivery.py](../backend/institutions/test_parent_push_delivery.py)
- [backend/institutions/test_payroll.py](../backend/institutions/test_payroll.py)
- [backend/institutions/test_pedagogical_calendar.py](../backend/institutions/test_pedagogical_calendar.py)
- [backend/institutions/test_persona_preschool_primary.py](../backend/institutions/test_persona_preschool_primary.py)
- [backend/institutions/test_platform.py](../backend/institutions/test_platform.py)
- [backend/institutions/test_platform_admin.py](../backend/institutions/test_platform_admin.py)
- [backend/institutions/test_platform_tariff_intervention.py](../backend/institutions/test_platform_tariff_intervention.py)
- [backend/institutions/test_preschool_followup.py](../backend/institutions/test_preschool_followup.py)
- [backend/institutions/test_registration.py](../backend/institutions/test_registration.py)
- [backend/institutions/test_reports.py](../backend/institutions/test_reports.py)
- [backend/institutions/test_school_branding.py](../backend/institutions/test_school_branding.py)
- [backend/institutions/test_school_governance.py](../backend/institutions/test_school_governance.py)
- [backend/institutions/test_school_profiles.py](../backend/institutions/test_school_profiles.py)
- [backend/institutions/test_singpay.py](../backend/institutions/test_singpay.py)
- [backend/institutions/test_staff.py](../backend/institutions/test_staff.py)
- [backend/institutions/test_staff_dossiers.py](../backend/institutions/test_staff_dossiers.py)
- [backend/institutions/test_staff_onboarding.py](../backend/institutions/test_staff_onboarding.py)
- [backend/institutions/test_staff_profiles.py](../backend/institutions/test_staff_profiles.py)
- [backend/institutions/test_student_access_permissions.py](../backend/institutions/test_student_access_permissions.py)
- [backend/institutions/test_students.py](../backend/institutions/test_students.py)
- [backend/institutions/test_subscriptions.py](../backend/institutions/test_subscriptions.py)
- [backend/institutions/test_teacher_journey.py](../backend/institutions/test_teacher_journey.py)
- [backend/institutions/test_teaching_diary.py](../backend/institutions/test_teaching_diary.py)
- [backend/institutions/test_tenant_functions.py](../backend/institutions/test_tenant_functions.py)
- [backend/institutions/test_timetables.py](../backend/institutions/test_timetables.py)
- [backend/institutions/tests.py](../backend/institutions/tests.py)
- [backend/pedagogy/test_pwa.py](../backend/pedagogy/test_pwa.py)
- [backend/pedagogy/tests.py](../backend/pedagogy/tests.py)
