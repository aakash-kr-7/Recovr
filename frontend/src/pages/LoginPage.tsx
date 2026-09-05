import React, { useState } from 'react';
import { useMerchant } from '@/context/MerchantContext';
import { useNavigate } from 'react-router-dom';

export function LoginPage() {
  const { setMerchantName } = useMerchant();
  const [name, setName] = useState('Acme Retail Pvt Ltd');
  const navigate = useNavigate();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (name.trim()) {
      setMerchantName(name.trim());
      navigate('/', { replace: true });
    }
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', backgroundColor: 'var(--surface-base, #f6f7f9)', padding: '20px' }}>
      <div style={{ background: 'var(--surface-raised, #fff)', padding: '40px', borderRadius: '12px', border: '1px solid var(--border-subtle, #e0e5ec)', width: '100%', maxWidth: '420px', textAlign: 'center', boxShadow: '0 4px 6px rgba(0,0,0,0.05)' }}>
        <img src="/logo.svg" alt="RECOVR Logo" style={{ width: '64px', height: '64px', marginBottom: '24px' }} />
        <h1 style={{ margin: '0 0 8px', fontSize: '24px', color: 'var(--text-primary, #172133)' }}>Welcome to RECOVR</h1>
        <p style={{ margin: '0 0 32px', color: 'var(--text-secondary, #687488)', fontSize: '14px' }}>AI-powered revenue recovery agent</p>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div style={{ textAlign: 'left' }}>
            <label htmlFor="merchantName" style={{ display: 'block', marginBottom: '8px', fontSize: '13px', fontWeight: 600, color: 'var(--chart-label, #435168)' }}>Operating as Merchant</label>
            <input
              id="merchantName"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              style={{ width: '100%', padding: '12px 14px', borderRadius: '6px', border: '1px solid var(--border-subtle, #e0e5ec)', fontSize: '14px', color: 'var(--text-primary, #172133)', outline: 'none', backgroundColor: 'transparent' }}
              onFocus={(e) => e.target.style.borderColor = 'var(--brand-primary, hsla(218, 100%, 63%, 1))'}
              onBlur={(e) => e.target.style.borderColor = 'var(--border-subtle, #e0e5ec)'}
            />
          </div>
          <button type="submit" style={{ padding: '12px', borderRadius: '6px', border: 'none', backgroundColor: 'var(--brand-primary, hsla(218, 100%, 63%, 1))', color: '#fff', fontSize: '14px', fontWeight: 600, cursor: 'pointer', transition: 'opacity 0.2s' }}
            onMouseOver={(e) => e.currentTarget.style.opacity = '0.9'}
            onMouseOut={(e) => e.currentTarget.style.opacity = '1'}
          >
            Continue to workspace
          </button>
        </form>
      </div>
    </div>
  );
}
