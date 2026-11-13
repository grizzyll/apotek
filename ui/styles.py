# ui/styles.py
# Desain Sistem Visual Terstandar untuk PT Sehat Bersama Farma

CUSTOM_CSS = """
<style>
    /* Global Typography & Colors */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Container Header */
    .app-header {
        background: linear-gradient(135deg, #0F766E 0%, #0D9488 50%, #14B8A6 100%);
        color: white;
        padding: 24px 28px;
        border-radius: 14px;
        margin-bottom: 24px;
        box-shadow: 0 4px 14px rgba(13, 148, 136, 0.15);
    }
    .app-header h2 {
        color: white !important;
        margin: 0 0 6px 0;
        font-weight: 700;
        font-size: 26px;
        letter-spacing: -0.5px;
    }
    .app-header p {
        color: #CCFBF1 !important;
        margin: 0;
        font-size: 14px;
        opacity: 0.95;
    }

    /* KPI Cards */
    .kpi-container {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 18px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .kpi-container:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
    }
    .kpi-label {
        font-size: 12px;
        font-weight: 600;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 6px;
    }
    .kpi-value {
        font-size: 24px;
        font-weight: 700;
        color: #0F172A;
    }
    .kpi-sub {
        font-size: 12px;
        color: #0D9488;
        font-weight: 500;
        margin-top: 4px;
    }

    /* Demo Cards for Tab 2 */
    .demo-box {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-left: 4px solid #0D9488;
        border-radius: 10px;
        padding: 16px 18px;
        margin-bottom: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    }
    .demo-box h4 {
        margin: 0 0 8px 0;
        color: #0F172A;
        font-size: 16px;
        font-weight: 600;
    }
    .demo-box p {
        font-size: 13px;
        color: #475569;
        margin: 0 0 10px 0;
        line-height: 1.5;
    }

    /* Badges */
    .badge-bebas {
        background-color: #DCFCE7;
        color: #166534;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
    }
    .badge-bebas-terbatas {
        background-color: #E0F2FE;
        color: #0369A1;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
    }
    .badge-keras {
        background-color: #FEE2E2;
        color: #991B1B;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
    }
    .badge-alkes {
        background-color: #F3E8FF;
        color: #6B21A8;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
    }

    /* Struk Digital */
    .receipt-box {
        background-color: #F8FAFC;
        border: 1px dashed #CBD5E1;
        border-radius: 8px;
        padding: 16px;
        font-family: 'Courier New', Courier, monospace;
        font-size: 13px;
        color: #1E293B;
        line-height: 1.4;
    }

    /* Login Box */
    .login-wrapper {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 16px;
        padding: 32px 28px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.03);
    }
    .login-icon {
        background: #CCFBF1;
        color: #0F766E;
        width: 64px;
        height: 64px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 32px;
        margin: 0 auto 16px auto;
    }
</style>
"""
