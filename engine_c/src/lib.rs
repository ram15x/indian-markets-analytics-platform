//! Engine C: the platform's measures written again in Rust, from the written conventions, so that a figure is shown
//! only when three implementations (numpy, DuckDB SQL, Rust) agree. Dates are days since 1970-01-01.
//! Conventions: as-of = last value on or before the date; years of 365 days; volatility = sample stdev of daily log
//! changes x sqrt(252); SIP buys at the first date on/after the scheduled day (clamped to month end); XIRR actual/365.

pub mod core {
    #[derive(Debug, PartialEq)]
    pub struct CErr(pub String);
    fn err<T>(m: impl Into<String>) -> Result<T, CErr> { Err(CErr(m.into())) }

    // ---- calendar (Howard Hinnant's days_from_civil / civil_from_days) ----
    pub fn civil(z: i64) -> (i64, u32, u32) {
        let z = z + 719_468;
        let era = z.div_euclid(146_097);
        let doe = z.rem_euclid(146_097);
        let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
        let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
        let mp = (5 * doy + 2) / 153;
        let d = (doy - (153 * mp + 2) / 5 + 1) as u32;
        let m = if mp < 10 { mp + 3 } else { mp - 9 } as u32;
        let y = yoe + era * 400 + if m <= 2 { 1 } else { 0 };
        (y, m, d)
    }
    pub fn days(y: i64, m: u32, d: u32) -> i64 {
        let y = if m <= 2 { y - 1 } else { y };
        let era = y.div_euclid(400);
        let yoe = y.rem_euclid(400);
        let mp = if m > 2 { m - 3 } else { m + 9 } as i64;
        let doy = (153 * mp + 2) / 5 + d as i64 - 1;
        let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
        era * 146_097 + doe - 719_468
    }
    pub fn month_len(y: i64, m: u32) -> u32 {
        let (ny, nm) = if m == 12 { (y + 1, 1) } else { (y, m + 1) };
        (days(ny, nm, 1) - days(y, m, 1)) as u32
    }
    /// Same day `months` earlier/later, clamped to the month's last day.
    pub fn add_months(day: i64, months: i64) -> i64 {
        let (y, m, d) = civil(day);
        let t = y * 12 + (m as i64 - 1) + months;
        let (ny, nm) = (t.div_euclid(12), (t.rem_euclid(12) + 1) as u32);
        days(ny, nm, d.min(month_len(ny, nm)))
    }

    /// Index of the last date <= day.
    pub fn asof(dates: &[i64], day: i64) -> Result<usize, CErr> {
        let n = dates.partition_point(|&x| x <= day);
        if n == 0 { return err(format!("no value on or before day {day}")); }
        Ok(n - 1)
    }

    pub fn total_return(dates: &[i64], v: &[f64], start: i64, end: i64) -> Result<(f64, usize, usize), CErr> {
        let (i, j) = (asof(dates, start)?, asof(dates, end)?);
        Ok((v[j] / v[i] - 1.0, i, j))
    }

    pub fn cagr(dates: &[i64], v: &[f64], start: i64, end: i64) -> Result<(f64, usize, usize), CErr> {
        let (t, i, j) = total_return(dates, v, start, end)?;
        let d = dates[j] - dates[i];
        if d <= 0 { return err("window has no elapsed days"); }
        Ok(((1.0 + t).powf(365.0 / d as f64) - 1.0, i, j))
    }

    /// (drawdown, peak index, trough index); earliest index on ties.
    pub fn max_drawdown(dates: &[i64], v: &[f64], start: i64, end: i64) -> Result<(f64, usize, usize), CErr> {
        let (i, j) = (asof(dates, start)?, asof(dates, end)?);
        let (mut peak, mut best, mut trough) = (v[i], 0.0_f64, i);
        for k in i..=j {
            if v[k] > peak { peak = v[k]; }
            let dd = v[k] / peak - 1.0;
            if dd < best { best = dd; trough = k; }
        }
        let mut p = i;
        for k in i..=trough { if v[k] > v[p] { p = k; } }
        Ok((best, p, trough))
    }

    /// (annualised volatility, number of changes). Two-pass mean and variance.
    pub fn volatility(dates: &[i64], v: &[f64], start: i64, end: i64) -> Result<(f64, usize), CErr> {
        let (i, j) = (asof(dates, start)?, asof(dates, end)?);
        if j < i + 2 { return err("fewer than 3 values in window"); }
        let lr: Vec<f64> = (i + 1..=j).map(|k| (v[k] / v[k - 1]).ln()).collect();
        let n = lr.len() as f64;
        let mean = lr.iter().sum::<f64>() / n;
        let var = lr.iter().map(|x| (x - mean) * (x - mean)).sum::<f64>() / (n - 1.0);
        Ok((var.sqrt() * 252f64.sqrt(), lr.len()))
    }

    /// Purchase indices: first date on/after each scheduled day (day of month, clamped) inside [start, end].
    pub fn sip_schedule(dates: &[i64], start: i64, end: i64, day: u32) -> Vec<usize> {
        let (mut y, mut m, _) = civil(start);
        let mut out = vec![];
        loop {
            let sched = days(y, m, day.min(month_len(y, m)));
            if sched > end { break; }
            if sched >= start {
                let i = dates.partition_point(|&x| x < sched);
                if i < dates.len() && dates[i] <= end { out.push(i); }
            }
            if m == 12 { y += 1; m = 1 } else { m += 1 }
        }
        out
    }

    fn npv(r: f64, t: &[f64], cf: &[f64]) -> f64 { t.iter().zip(cf).map(|(t, c)| c / (1.0 + r).powf(*t)).sum() }
    fn dnpv(r: f64, t: &[f64], cf: &[f64]) -> f64 { t.iter().zip(cf).map(|(t, c)| -c * t / (1.0 + r).powf(t + 1.0)).sum() }

    /// XIRR by a safeguarded Newton step inside a shrinking bracket (falls back to bisection when Newton leaves it).
    pub fn xirr(t: &[f64], cf: &[f64]) -> Result<f64, CErr> {
        let (mut lo, mut hi) = (-0.9999_f64, 1000.0_f64);
        let (flo, fhi) = (npv(lo, t, cf), npv(hi, t, cf));
        if !flo.is_finite() || !fhi.is_finite() || flo * fhi > 0.0 { return err("XIRR not bracketed"); }
        let mut r = 0.1_f64.clamp(lo, hi);
        for _ in 0..1000 {
            let f = npv(r, t, cf);
            if f == 0.0 { return Ok(r); }
            if (f > 0.0) == (flo > 0.0) { lo = r } else { hi = r }
            let d = dnpv(r, t, cf);
            let nr = r - f / d;
            let next = if d != 0.0 && nr.is_finite() && nr > lo && nr < hi { nr } else { 0.5 * (lo + hi) };
            if (next - r).abs() <= 1e-15 * (1.0 + r.abs()) || hi - lo <= 1e-15 * (1.0 + r.abs()) { return Ok(next); }
            r = next;
        }
        err("XIRR did not converge")
    }

    /// (xirr, invested, final value, instalments)
    pub fn sip_xirr(dates: &[i64], v: &[f64], amount: f64, start: i64, end: i64, day: u32) -> Result<(f64, f64, f64, usize), CErr> {
        let idx = sip_schedule(dates, start, end, day);
        if idx.len() < 2 { return err("fewer than 2 instalments in window"); }
        let j = asof(dates, end)?;
        let units: f64 = idx.iter().map(|&i| amount / v[i]).sum();
        let fin = units * v[j];
        let d0 = dates[idx[0]];
        let mut t: Vec<f64> = idx.iter().map(|&i| (dates[i] - d0) as f64 / 365.0).collect();
        let mut cf = vec![-amount; idx.len()];
        t.push((dates[j] - d0) as f64 / 365.0); cf.push(fin);
        Ok((xirr(&t, &cf)?, amount * idx.len() as f64, fin, idx.len()))
    }

    pub struct Rolling { pub median: f64, pub min: f64, pub max: f64, pub pct_negative: f64, pub latest: f64, pub n: usize,
                         pub first_end: i64, pub last_end: i64, pub min_end: i64, pub max_end: i64 }

    pub fn rolling(dates: &[i64], v: &[f64], start: i64, end: i64, years: u32) -> Result<Rolling, CErr> {
        let first = dates[0];
        let mut out: Vec<(i64, f64)> = vec![];
        for (k, &e) in dates.iter().enumerate() {
            if e < start || e > end { continue; }
            let b = add_months(e, -12 * years as i64);
            if b < first { continue; }
            let i = asof(dates, b)?;
            out.push((e, (v[k] / v[i]).powf(1.0 / years as f64) - 1.0));
        }
        if out.is_empty() { return err(format!("history is shorter than {years} years")); }
        let mut s: Vec<f64> = out.iter().map(|x| x.1).collect();
        s.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let n = s.len();
        let median = if n % 2 == 1 { s[n / 2] } else { 0.5 * (s[n / 2 - 1] + s[n / 2]) };
        let (mut mi, mut ma) = (0usize, 0usize);
        for (k, x) in out.iter().enumerate() {
            if x.1 < out[mi].1 { mi = k; }
            if x.1 > out[ma].1 { ma = k; }
        }
        Ok(Rolling { median, min: out[mi].1, max: out[ma].1, pct_negative: out.iter().filter(|x| x.1 < 0.0).count() as f64 / n as f64,
                     latest: out[n - 1].1, n, first_end: out[0].0, last_end: out[n - 1].0, min_end: out[mi].0, max_end: out[ma].0 })
    }
    pub const MIN_RETURNS: usize = 120;
    pub const RF_MAX_STALE: i64 = 28;

    /// Daily excess returns (NAV return minus the T-bill rate for that period) and the mean yield used.
    pub fn excess(dates: &[i64], v: &[f64], rf_d: &[i64], rf_y: &[f64], start: i64, end: i64) -> Result<(Vec<f64>, f64, i64, i64), CErr> {
        let (i, j) = (asof(dates, start)?, asof(dates, end)?);
        if j < i + MIN_RETURNS { return err(format!("fewer than {MIN_RETURNS} daily returns in window")); }
        let (mut out, mut ysum) = (Vec::with_capacity(j - i), 0.0);
        for k in i + 1..=j {
            let prev = dates[k - 1];
            let q = rf_d.partition_point(|&x| x <= prev);
            if q == 0 { return err(format!("no risk-free rate on or before day {prev}")); }
            let age = prev - rf_d[q - 1];
            if age > RF_MAX_STALE { return err(format!("risk-free rate is {age} days old (limit {RF_MAX_STALE})")); }
            let y = rf_y[q - 1];
            let rf = y / 100.0 * (dates[k] - prev) as f64 / 365.0;      // simple accrual, actual/365 as RBI quotes it
            out.push(v[k] / v[k - 1] - 1.0 - rf);
            ysum += y;
        }
        let n = out.len() as f64;
        Ok((out, ysum / n, dates[i], dates[j]))
    }

    /// (sharpe, sortino, n, mean yield). Sortino is None when no day fell short of the risk-free rate.
    pub fn sharpe_sortino(dates: &[i64], v: &[f64], rf_d: &[i64], rf_y: &[f64], start: i64, end: i64)
        -> Result<(Option<f64>, Option<f64>, usize, f64, i64, i64), CErr> {
        let (e, ym, d0, d1) = excess(dates, v, rf_d, rf_y, start, end)?;
        let n = e.len() as f64;
        let mean = e.iter().sum::<f64>() / n;
        let sd = (e.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / (n - 1.0)).sqrt();
        let dd = (e.iter().map(|x| x.min(0.0).powi(2)).sum::<f64>() / n).sqrt();
        let k = 252f64.sqrt();
        Ok(((sd > 0.0).then(|| mean / sd * k), (dd > 0.0).then(|| mean / dd * k), e.len(), ym, d0, d1))
    }
}

#[cfg(feature = "python")]
mod py {
    use super::core as c;
    use pyo3::exceptions::PyValueError;
    use pyo3::prelude::*;
    use pyo3::types::PyDict;

    fn e(x: c::CErr) -> PyErr { PyValueError::new_err(x.0) }
    fn chk(d: &[i64], v: &[f64]) -> PyResult<()> {
        if d.is_empty() || d.len() != v.len() { return Err(PyValueError::new_err("dates and values must be non-empty and equal length")); }
        if d.windows(2).any(|w| w[0] >= w[1]) { return Err(PyValueError::new_err("dates must be strictly increasing")); }
        if v.iter().any(|x| !x.is_finite() || *x <= 0.0) { return Err(PyValueError::new_err("values must be finite and positive")); }
        Ok(())
    }

    #[pyfunction]
    fn total_return(py: Python<'_>, d: Vec<i64>, v: Vec<f64>, start: i64, end: i64) -> PyResult<Py<PyDict>> {
        chk(&d, &v)?; let (x, i, j) = c::total_return(&d, &v, start, end).map_err(e)?;
        let o = PyDict::new(py); o.set_item("value", x)?; o.set_item("start_day", d[i])?; o.set_item("end_day", d[j])?;
        o.set_item("start_value", v[i])?; o.set_item("end_value", v[j])?; Ok(o.into())
    }
    #[pyfunction]
    fn cagr(py: Python<'_>, d: Vec<i64>, v: Vec<f64>, start: i64, end: i64) -> PyResult<Py<PyDict>> {
        chk(&d, &v)?; let (x, i, j) = c::cagr(&d, &v, start, end).map_err(e)?;
        let o = PyDict::new(py); o.set_item("value", x)?; o.set_item("start_day", d[i])?; o.set_item("end_day", d[j])?;
        o.set_item("days", d[j] - d[i])?; Ok(o.into())
    }
    #[pyfunction]
    fn max_drawdown(py: Python<'_>, d: Vec<i64>, v: Vec<f64>, start: i64, end: i64) -> PyResult<Py<PyDict>> {
        chk(&d, &v)?; let (x, p, t) = c::max_drawdown(&d, &v, start, end).map_err(e)?;
        let o = PyDict::new(py); o.set_item("value", x)?; o.set_item("peak_day", d[p])?; o.set_item("trough_day", d[t])?; Ok(o.into())
    }
    #[pyfunction]
    fn volatility(py: Python<'_>, d: Vec<i64>, v: Vec<f64>, start: i64, end: i64) -> PyResult<Py<PyDict>> {
        chk(&d, &v)?; let (x, n) = c::volatility(&d, &v, start, end).map_err(e)?;
        let o = PyDict::new(py); o.set_item("value", x)?; o.set_item("n", n)?; Ok(o.into())
    }
    #[pyfunction]
    fn sip_xirr(py: Python<'_>, d: Vec<i64>, v: Vec<f64>, amount: f64, start: i64, end: i64, day: u32) -> PyResult<Py<PyDict>> {
        chk(&d, &v)?;
        if !(1..=31).contains(&day) || !(amount.is_finite() && amount > 0.0) { return Err(PyValueError::new_err("bad SIP day or amount")); }
        let (x, inv, fin, n) = c::sip_xirr(&d, &v, amount, start, end, day).map_err(e)?;
        let o = PyDict::new(py); o.set_item("value", x)?; o.set_item("invested", inv)?; o.set_item("final_value", fin)?; o.set_item("n", n)?;
        Ok(o.into())
    }
    #[pyfunction]
    fn rolling_return(py: Python<'_>, d: Vec<i64>, v: Vec<f64>, start: i64, end: i64, years: u32) -> PyResult<Py<PyDict>> {
        chk(&d, &v)?;
        if !(1..=20).contains(&years) { return Err(PyValueError::new_err("years must be 1-20")); }
        let r = c::rolling(&d, &v, start, end, years).map_err(e)?;
        let o = PyDict::new(py);
        for (k, x) in [("value", r.median), ("min", r.min), ("max", r.max), ("pct_negative", r.pct_negative), ("latest", r.latest)] { o.set_item(k, x)?; }
        for (k, x) in [("first_end_day", r.first_end), ("last_end_day", r.last_end), ("min_end_day", r.min_end), ("max_end_day", r.max_end)] { o.set_item(k, x)?; }
        o.set_item("n", r.n)?; Ok(o.into())
    }

    #[pyfunction]
    fn sharpe_sortino(py: Python<'_>, d: Vec<i64>, v: Vec<f64>, rf_d: Vec<i64>, rf_y: Vec<f64>, start: i64, end: i64) -> PyResult<Py<PyDict>> {
        chk(&d, &v)?;
        if rf_d.is_empty() || rf_d.len() != rf_y.len() || rf_d.windows(2).any(|w| w[0] >= w[1]) || rf_y.iter().any(|y| !y.is_finite()) {
            return Err(PyValueError::new_err("risk-free dates must be increasing and yields finite"));
        }
        let (sh, so, n, ym, d0, d1) = c::sharpe_sortino(&d, &v, &rf_d, &rf_y, start, end).map_err(e)?;
        let o = PyDict::new(py); o.set_item("sharpe", sh)?; o.set_item("sortino", so)?; o.set_item("n", n)?; o.set_item("mean_rf", ym)?;
        o.set_item("start_day", d0)?; o.set_item("end_day", d1)?;
        Ok(o.into())
    }

    #[pymodule]
    fn imap_engine_c(m: &Bound<'_, PyModule>) -> PyResult<()> {
        for f in [wrap_pyfunction!(total_return, m)?, wrap_pyfunction!(cagr, m)?, wrap_pyfunction!(max_drawdown, m)?,
                  wrap_pyfunction!(volatility, m)?, wrap_pyfunction!(sip_xirr, m)?, wrap_pyfunction!(rolling_return, m)?, wrap_pyfunction!(sharpe_sortino, m)?] {
            m.add_function(f)?;
        }
        m.add("VERSION", env!("CARGO_PKG_VERSION"))?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::core::*;
    #[test] fn calendar_round_trips() {
        for z in -800_000..800_000 { let (y, m, d) = civil(z); assert_eq!(days(y, m, d), z); }
        assert_eq!(days(1970, 1, 1), 0); assert_eq!(days(2000, 3, 1), 11_017);
        assert_eq!(month_len(2024, 2), 29); assert_eq!(month_len(2100, 2), 28); assert_eq!(month_len(2000, 2), 29);
    }
    #[test] fn months_clamp_to_month_end() {
        assert_eq!(add_months(days(2024, 3, 31), -1), days(2024, 2, 29));
        assert_eq!(add_months(days(2023, 2, 28), -12), days(2022, 2, 28));
        assert_eq!(add_months(days(2024, 2, 29), -12), days(2023, 2, 28));
        assert_eq!(add_months(days(2020, 1, 15), -36), days(2017, 1, 15));
    }
    #[test] fn xirr_known_value() {
        // -1000 now, +1100 after exactly 365 days -> 10%
        let r = xirr(&[0.0, 1.0], &[-1000.0, 1100.0]).unwrap();
        assert!((r - 0.1).abs() < 1e-12, "{r}");
    }
    #[test] fn sharpe_constant_excess_and_stale_rate() {
        // NAV grows 0.1% a day, rate 0%: excess constant -> stdev 0 -> Sharpe None, Sortino None
        let d: Vec<i64> = (0..200).collect(); let v: Vec<f64> = (0..200).map(|k| 1.001f64.powi(k)).collect();
        assert!(sharpe_sortino(&d, &v, &[0], &[0.0], 0, 199).is_err(), "a rate from day 0 is too old by day 15");
        let rf_d: Vec<i64> = (0..200).step_by(7).collect(); let rf_y = vec![0.0; rf_d.len()];
        let (sh, so, n, ym, _, _) = sharpe_sortino(&d, &v, &rf_d, &rf_y, 0, 199).unwrap();
        assert_eq!((n, ym), (199, 0.0)); assert!(so.is_none());
        assert!(sh.is_none() || sh.unwrap() > 1e6, "constant excess: stdev 0 or rounding-level");
    }
    #[test] fn drawdown_and_vol_small() {
        let d = [0, 1, 2, 3, 4]; let v = [10.0, 12.0, 9.0, 11.0, 13.0];
        let (dd, p, t) = max_drawdown(&d, &v, 0, 4).unwrap();
        assert!((dd - (9.0 / 12.0 - 1.0)).abs() < 1e-15); assert_eq!((p, t), (1, 2));
        assert!(volatility(&d, &v, 0, 1).is_err());
    }
}
