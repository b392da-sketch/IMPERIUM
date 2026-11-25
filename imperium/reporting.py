"""Descriptive and paired statistics for EF09-RH1 evidence."""

from functools import cache
from math import exp, lgamma, log, log1p, pi, sqrt
from statistics import mean, median, stdev


def describe(values):
    """P10/P90 use linear interpolation at index (n-1)*p (type 7)."""
    ordered = sorted(values)
    count = len(ordered)

    def quantile(probability):
        index = (count - 1) * probability
        lower = int(index)
        other = min(lower + 1, count - 1)
        return ordered[lower] + (index - lower) * (ordered[other] - ordered[lower])

    return {
        "n": count,
        "mean": mean(ordered) if count else None,
        "sample_sd": stdev(ordered) if count > 1 else None,
        "median": median(ordered) if count else None,
        "p10": quantile(.10) if count else None,
        "p90": quantile(.90) if count else None,
    }


@cache
def t_critical_95(df):
    """Invert the Student t CDF by adaptive integration and bisection."""
    if df < 1:
        raise ValueError("Student t requires positive degrees of freedom")
    log_scale = lgamma((df + 1) / 2) - lgamma(df / 2) - .5 * log(df * pi)

    def density(x):
        return exp(log_scale - ((df + 1) / 2) * log1p(x * x / df))

    def integral_to(x):
        def integrate(a, b, fa, fm, fb, estimate, tolerance, depth):
            mid = (a + b) / 2
            left_mid = density((a + mid) / 2)
            right_mid = density((mid + b) / 2)
            left = (mid - a) * (fa + 4 * left_mid + fm) / 6
            right = (b - mid) * (fm + 4 * right_mid + fb) / 6
            residual = left + right - estimate
            if abs(residual) <= 15 * tolerance or not depth:
                return left + right + residual / 15
            return (integrate(a, mid, fa, left_mid, fm, left, tolerance / 2, depth - 1)
                    + integrate(mid, b, fm, right_mid, fb, right, tolerance / 2, depth - 1))

        fa, fm, fb = density(0), density(x / 2), density(x)
        return integrate(0, x, fa, fm, fb, x * (fa + 4 * fm + fb) / 6, 1e-12, 24)

    # For integral over (0,x), .475 is the upper endpoint of a central 95% interval.
    lo, hi = 0., 16.
    for _ in range(45):
        mid = (lo + hi) / 2
        if integral_to(mid) < .475:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def paired_continuous(values):
    result = describe(values)
    n, average, sd = result["n"], result["mean"], result["sample_sd"]
    result["student_t_95"] = None
    if sd is not None:
        margin = t_critical_95(n - 1) * sd / sqrt(n) if sd else 0
        result["student_t_95"] = [average - margin, average + margin]
    return result
